import json

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from propifai.mapeo_ubicaciones import DISTRITOS, obtener_nombre_distrito
from propifai.models import PropifaiProperty, PropertyType, User

from .constants import DOCUMENTATION_DOCUMENT_TYPES, STAGES
from .external_sources import (
    fetch_external_evidence,
    property_ids_for_fact_view,
    resolve_propifai_media_url,
    summarize_evidence,
)
from .models import PropertyWorkflow, StageRequirement, WorkflowEvent
from .services import duration_hours, ensure_workflow, gate_state, stage_progress, transition


def _safe_map(model, label):
    try:
        return {obj.id: getattr(obj, label, str(obj)) for obj in model.objects.using("propifai").all()}
    except Exception:
        return {}


def _fact_card(definition, summary):
    key = definition.key
    base = {"definition": definition, "status": "pending", "progress": 0, "duration": 0, "sla": definition.sla_hours, "done": 0, "total": 0, "area": definition.area, "blocked_reason": "", "source": "dbpropify_be", "evidence_at": None}
    documents = summary["documents"]
    if key in {"captation", "draft"}:
        base.update(status="completed", progress=100)
    elif key == "documentation":
        required_codes = {code for code, _label in DOCUMENTATION_DOCUMENT_TYPES}
        required_documents = [
            item for item in documents
            if str(item.get("document_code") or "").strip() in required_codes
        ]
        present_codes = {
            str(item.get("document_code") or "").strip()
            for item in required_documents
            if item.get("file") or item.get("file_url")
        }
        done = len(present_codes)
        progress = (0, 33, 67, 100)[done]
        base.update(
            status="completed" if done == 3 else "in_progress" if done else "pending",
            progress=progress,
            done=done,
            total=3,
            evidence_at=min(
                (item.get("created_at") for item in required_documents if item.get("created_at")),
                default=None,
            ),
        )
    elif key == "legal_review":
        reviewed = summary["reviewed_documents"]
        base.update(status="completed" if documents and len(reviewed) == len(documents) else "in_progress" if reviewed else "pending", progress=round(len(reviewed) * 100 / len(documents)) if documents else 0, done=len(reviewed), total=len(documents), evidence_at=max((item.get("legal_reviewed_at") for item in reviewed if item.get("legal_reviewed_at")), default=None))
    elif key == "brokerage_contract":
        contract = summary["contract"]
        base.update(status="completed" if contract else "pending", progress=100 if contract else 0, done=1 if contract else 0, total=1, evidence_at=contract.get("created_at") if contract else None)
    elif key == "marketing":
        media = summary["media"]
        progress = min(100, len(media) * 20)
        base.update(status="completed" if media else "pending", progress=progress, done=len(media), total=max(5, len(media)), evidence_at=summary["media_first"])
    elif key == "publication":
        base.update(status="completed" if summary["published"] else "pending", progress=100 if summary["published"] else 0, done=1 if summary["published"] else 0, total=1, evidence_at=summary["publication_at"])
    elif key == "advertising":
        base.update(status="disabled", source="Sin fuente conectada")
    elif key == "visits":
        visits = summary["visits"]
        base.update(status="completed" if visits else "pending", progress=100 if visits else 0, done=len(visits), total=len(visits), evidence_at=summary["visit_first"])
    elif key == "offer":
        proposals = summary["proposals"]
        base.update(status="completed" if proposals else "pending", progress=100 if proposals else 0, done=len(proposals), total=len(proposals), evidence_at=summary["proposal_first"])
    elif key == "accepted_offer":
        accepted = summary["accepted_proposals"]
        base.update(status="completed" if accepted else "pending", progress=100 if accepted else 0, done=len(accepted), total=len(summary["proposals"]), evidence_at=min((item.get("responded_at") for item in accepted if item.get("responded_at")), default=None))
    elif key == "notary":
        facts = summary["notary_events"]
        base.update(status="completed" if facts else "pending", progress=100 if facts else 0, done=len(facts), total=len(facts), evidence_at=min((item.get("start_time") or item.get("created_at") for item in facts), default=None))
    elif key in {"disbursement", "closed"}:
        facts = summary["closings"]
        base.update(status="completed" if facts else "pending", progress=100 if facts else 0, done=len(facts), total=len(facts), evidence_at=min((item.get("start_time") or item.get("created_at") for item in facts), default=None))
    return base


def dashboard(request):
    queryset = PropifaiProperty.objects.using("propifai").all().order_by("-updated_at", "-id")
    quick_view = request.GET.get("view", "all").strip()
    district = request.GET.get("district", "").strip()
    property_type = request.GET.get("property_type", "").strip()
    responsible = request.GET.get("responsible", "").strip()
    price_min = request.GET.get("price_min", "").strip()
    price_max = request.GET.get("price_max", "").strip()
    if district.isdigit():
        queryset = queryset.filter(district_id=int(district))
    if property_type.isdigit():
        queryset = queryset.filter(property_type_id=int(property_type))
    if responsible.isdigit():
        queryset = queryset.filter(responsible_id=int(responsible))
    if quick_view == "draft":
        queryset = queryset.filter(wp_post_id__isnull=True)
    elif quick_view == "published":
        queryset = queryset.filter(wp_post_id__isnull=False)
    elif quick_view in {"visits", "offer", "closed", "ready"}:
        queryset = queryset.filter(id__in=property_ids_for_fact_view(quick_view) or [])
    elif quick_view in {"blocked", "overdue"}:
        status = "blocked" if quick_view == "blocked" else "overdue"
        ids = PropertyWorkflow.objects.filter(stages__status=status).values_list("property_id", flat=True).distinct()
        queryset = queryset.filter(id__in=list(ids))
    try:
        if price_min:
            queryset = queryset.filter(price__gte=float(price_min))
        if price_max:
            queryset = queryset.filter(price__lte=float(price_max))
    except ValueError:
        pass

    paginator = Paginator(queryset, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    property_ids = [item.id for item in page_obj.object_list]
    external_evidence = fetch_external_evidence(property_ids)
    workflows = {
        item.property_id: item
        for item in PropertyWorkflow.objects.filter(property_id__in=property_ids)
        .prefetch_related("stages__requirements", "parallel_tasks")
    }
    users = _safe_map(User, "nombre_completo")
    types = _safe_map(PropertyType, "name")
    rows = []
    for prop in page_obj.object_list:
        workflow = workflows.get(prop.id)
        summary = summarize_evidence(prop, external_evidence[prop.id])
        stage_cards = [_fact_card(definition, summary) for definition in STAGES]
        primary_media = next((item for item in summary["images"] if item.get("resolved_url")), None)
        general_status = "Cerrada" if summary["closings"] else "Publicada" if summary["published"] else "Borrador"
        fact_score = round(sum(card["progress"] for card in stage_cards if card["status"] != "disabled") / max(1, sum(card["status"] != "disabled" for card in stage_cards)))
        rows.append({
            "property": prop,
            "district": obtener_nombre_distrito(prop.district_id) if prop.district_id else "Sin distrito",
            "property_type": types.get(prop.property_type_id, "Sin tipo"),
            "responsible": users.get(prop.responsible_id, "Sin responsable"),
            "workflow": workflow,
            "stage_cards": stage_cards,
            "summary": summary,
            "primary_image": primary_media.get("preview_url") if primary_media else "",
            "general_status": general_status,
            "fact_score": fact_score,
        })

    all_workflows = PropertyWorkflow.objects.all()
    metrics = {
        "visible": paginator.count,
        "draft": PropifaiProperty.objects.using("propifai").filter(wp_post_id__isnull=True).count(),
        "blocked": all_workflows.filter(stages__status="blocked").distinct().count(),
        "overdue": all_workflows.filter(stages__status="overdue").distinct().count(),
        "ready": len(property_ids_for_fact_view("ready") or []),
        "score": round(sum(item["fact_score"] for item in rows) / len(rows)) if rows else 0,
    }
    return render(request, "property_traceability/dashboard.html", {
        "rows": rows,
        "stages": STAGES,
        "metrics": metrics,
        "page_obj": page_obj,
        "query": request.GET,
        "property_types": sorted(types.items(), key=lambda item: item[1]),
        "responsibles": sorted(users.items(), key=lambda item: item[1]),
        "districts": sorted(((key, value) for key, value in DISTRITOS.items()), key=lambda item: item[1]),
        "active_view": quick_view,
    })


@require_GET
def workflow_detail(request, property_id):
    try:
        prop = PropifaiProperty.objects.using("propifai").get(id=property_id)
    except PropifaiProperty.DoesNotExist:
        return JsonResponse({"error": "La propiedad no existe en dbpropify_be"}, status=404)
    external = summarize_evidence(prop, fetch_external_evidence([property_id])[property_id])
    try:
        workflow = PropertyWorkflow.objects.prefetch_related(
            "stages__requirements", "parallel_tasks", "events"
        ).get(property_id=property_id)
    except PropertyWorkflow.DoesNotExist:
        workflow = None
    now = timezone.now()
    stages = []
    if workflow:
        for execution in workflow.stages.all():
            allowed, missing = gate_state(workflow, execution.stage_key)
            requirements = [{
                "id": item.id,
                "code": item.code,
                "label": item.label,
                "mandatory": item.is_mandatory,
                "status": item.status,
            } for item in execution.requirements.all()]
            stages.append({
                "key": execution.stage_key,
                "status": execution.status,
                "progress": stage_progress(execution),
                "duration_hours": duration_hours(execution, now),
                "due_at": execution.due_at,
                "area": execution.area,
                "blocked_reason": execution.blocked_reason,
                "transition_allowed": allowed,
                "missing_gates": missing,
                "requirements": requirements,
            })
    return JsonResponse({
        "initialized": workflow is not None,
        "property_id": property_id,
        "current_stage": workflow.current_stage if workflow else None,
        "general_status": workflow.general_status if workflow else None,
        "sellability_score": workflow.sellability_score if workflow else 0,
        "stages": stages,
        "external": {
            "property": {
                "id": prop.id,
                "code": prop.code,
                "title": prop.title,
                "created_at": prop.created_at,
                "updated_at": prop.updated_at,
                "description": prop.description,
                "price": prop.price,
                "display_address": prop.display_address,
                "map_address": prop.map_address,
                "registry_number": prop.registry_number,
                "is_visible": prop.is_visible,
                "wp_post_id": prop.wp_post_id,
                "wp_slug": prop.wp_slug,
                "wp_last_sync": prop.wp_last_sync,
                "video_url": resolve_propifai_media_url(prop.video_url),
                "contact_id": prop.contact_id,
                "responsible_id": prop.responsible_id,
                "property_status_id": prop.property_status_id,
            },
            "documents": external["documents"],
            "documentation_types": [
                {"code": code, "label": label, "contribution": 33}
                for code, label in DOCUMENTATION_DOCUMENT_TYPES
            ],
            "media": external["media"],
            "events": external["events"],
            "proposals": external["proposals"],
            "published": external["published"],
            "publication_at": external["publication_at"],
        },
    })


@require_POST
def initialize_workflow(request, property_id):
    if not PropifaiProperty.objects.using("propifai").filter(id=property_id).exists():
        return JsonResponse({"error": "La propiedad no existe en dbpropify_be"}, status=404)
    user = getattr(request, "user", None)
    actor_id = getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None
    workflow = ensure_workflow(property_id, actor_id=actor_id)
    return JsonResponse({"ok": True, "workflow_id": workflow.id, "property_id": property_id})


@require_POST
def transition_workflow(request, property_id):
    try:
        payload = json.loads(request.body or "{}")
        workflow = PropertyWorkflow.objects.get(property_id=property_id)
        user = getattr(request, "user", None)
        actor_id = getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None
        transition(
            workflow,
            payload.get("target_stage", ""),
            actor_id=actor_id,
            reason=payload.get("reason", ""),
        )
        return JsonResponse({"ok": True, "current_stage": workflow.current_stage})
    except PropertyWorkflow.DoesNotExist:
        return JsonResponse({"error": "La propiedad todavía no tiene workflow"}, status=404)
    except (ValueError, json.JSONDecodeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)


@require_POST
def update_requirement(request, property_id, requirement_id):
    try:
        payload = json.loads(request.body or "{}")
        requirement = StageRequirement.objects.select_related("stage__workflow").get(
            id=requirement_id,
            stage__workflow__property_id=property_id,
        )
        new_status = payload.get("status", "")
        valid_statuses = {value for value, _ in StageRequirement.STATUS_CHOICES}
        if new_status not in valid_statuses:
            raise ValueError("Estado de requisito inválido")
        now = timezone.now()
        requirement.status = new_status
        if new_status == "requested" and not requirement.requested_at:
            requirement.requested_at = now
        if new_status == "received" and not requirement.received_at:
            requirement.received_at = now
        if new_status == "approved" and not requirement.approved_at:
            requirement.approved_at = now
        requirement.save()
        user = getattr(request, "user", None)
        actor_id = getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None
        WorkflowEvent.objects.create(
            workflow=requirement.stage.workflow,
            event_type="requirement_updated",
            from_stage=requirement.stage.stage_key,
            to_stage=requirement.stage.stage_key,
            actor_id=actor_id,
            area=requirement.stage.area,
            occurred_at=now,
            metadata={"requirement": requirement.code, "status": new_status},
        )
        return JsonResponse({
            "ok": True,
            "requirement_id": requirement.id,
            "status": requirement.status,
            "stage_progress": stage_progress(requirement.stage),
        })
    except StageRequirement.DoesNotExist:
        return JsonResponse({"error": "Requisito no encontrado"}, status=404)
    except (ValueError, json.JSONDecodeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
