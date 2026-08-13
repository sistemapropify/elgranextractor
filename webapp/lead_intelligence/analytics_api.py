# analytics_api.py
#
# Endpoints JSON de analítica de leads para consumo externo (ej. el backend
# DRF del CRM, vía su proxy server-to-server con X-Analytics-API-Key).
# Separado de views.py a propósito: ese archivo es el que se sigue
# extendiendo activamente con el motor IA/dashboards, así que las vistas
# nuevas de este puente viven acá para no aumentar su superficie de cambio.
#
# Reusa de views.py: analytics_access_required (sesión gerencia O API key,
# ya existía ahí junto a management_access_required, que extiende) y
# _parameters (parseo de from/to/cohort compartido por todos los dashboards).
import json
from datetime import datetime, time as dt_time

from django.db import connections
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import LeadConversationAssessment
from .property_dashboard import get_property_dashboard
from .services import (
    _dict_rows,
    get_attention_quality_dashboard,
    get_hourly_agent_matrix,
)
from .views import (
    _has_fresh_running_run,
    _parameters,
    analytics_access_required,
)
from .visit_resolution import resolve_visits_for_leads


@analytics_access_required
@require_GET
def hourly_agent_matrix_api(request):
    date_from, date_to, _ = _parameters(request)
    data = get_hourly_agent_matrix(date_from, date_to)
    return JsonResponse(data)


@analytics_access_required
@require_GET
def attention_quality_api(request):
    date_from, date_to, _ = _parameters(request)
    data = get_attention_quality_dashboard(
        date_from, date_to, request.GET.get("agent")
    )
    flagged = [
        {
            "lead_id": item["lead_id"],
            "display_name": item["display_name"],
            "agent_name": item["agent_name"],
            "issues": item.get("issues", []),
            "attention_overdue": bool(item.get("attention_overdue")),
            "quality_status": item.get("quality_status"),
        }
        for item in data["flagged_leads"]
    ]
    return JsonResponse(
        {
            "generated_at": data["generated_at"].isoformat(),
            "date_from": str(data["date_from"]),
            "date_to": str(data["date_to"]),
            "analysis_version": data["analysis_version"],
            "selected_agent_id": data["selected_agent_id"],
            "agent_options": [
                {"agent_id": agent_id, "agent_name": agent_name}
                for agent_id, agent_name in data["agent_options"]
            ],
            "agent_rows": data["agent_rows"],
            "overall": data["overall"],
            "flagged": flagged,
        }
    )


@analytics_access_required
@require_GET
def property_dashboard_api(request):
    date_from, date_to, _ = _parameters(request)
    data = get_property_dashboard(date_from, date_to, request.GET)
    return JsonResponse(
        {
            "generated_at": data["generated_at"].isoformat(),
            "date_from": str(data["date_from"]),
            "date_to": str(data["date_to"]),
            "filters": data["filters"],
            "filter_options": data["filter_options"],
            "cards": data["cards"],
            "summary": data["summary"],
            "portfolio_comparison": data["portfolio_comparison"],
            "collection_found": data["collection_found"],
        }
    )


@csrf_exempt
@analytics_access_required
@require_POST
def evaluacion_automatica(request):
    """Dispara una evaluación incremental de leads (canales programada/tiempo real).

    Es el disparador que usa el cron de GitHub Actions (header
    ``X-Analytics-API-Key``, mismo mecanismo que los endpoints de analítica del
    puente externo del CRM). Cuerpo JSON opcional:
        {"stages": "entered"|"contacted"|"bidirectional",
         "lookback_hours": 24,
         "workers": 2}
    Responde 202 al instante; la evaluación corre en un hilo en segundo plano y
    su progreso se ve en "Ejecuciones del analizador" (AnalysisRun/Steps).
    """
    from django.core.management import call_command

    from .management.commands.analyze_lead_conversations import reset_cancel

    try:
        payload = json.loads(request.body or b"{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}

    stages = str(payload.get("stages") or "entered")
    if stages not in ("entered", "contacted", "bidirectional"):
        return JsonResponse(
            {"status": "error", "detail": "stages inválido"},
            status=400,
        )
    try:
        lookback_hours = int(payload.get("lookback_hours") or 0)
        workers = int(payload.get("workers") or 2)
    except (TypeError, ValueError):
        return JsonResponse(
            {"status": "error", "detail": "lookback_hours/workers deben ser enteros"},
            status=400,
        )
    if workers < 1 or workers > 8:
        return JsonResponse(
            {"status": "error", "detail": "workers debe estar entre 1 y 8"},
            status=400,
        )

    # Evita superponer evaluaciones (el cron corre cada 15 min y la programada
    # puede tardar más de una pasada): si ya hay un run activo, se omite.
    if _has_fresh_running_run(clean_stale=True):
        return JsonResponse(
            {
                "status": "already_running",
                "stages": stages,
                "lookback_hours": lookback_hours,
            },
            status=202,
        )

    reset_cancel()

    def _ejecutar():
        from io import StringIO

        from django.db import close_old_connections

        close_old_connections()
        try:
            buf = StringIO()
            call_command(
                "analyze_lead_conversations",
                stages=stages,
                lookback_hours=lookback_hours,
                workers=workers,
                stdout=buf,
                stderr=buf,
            )
        finally:
            close_old_connections()

    from threading import Thread

    Thread(target=_ejecutar, daemon=True).start()
    return JsonResponse(
        {"status": "started", "stages": stages, "lookback_hours": lookback_hours},
        status=202,
    )


def get_visit_intent_leads(date_from, date_to, status="confirmed", agent_id=None, limit=100):
    """Leads con intención de visita confirmada por la IA, enriquecidos con el CRM.

    Fuente: ``LeadConversationAssessment`` (BD default) con
    ``visit_intent_status`` (resultado del análisis IA/determinista de
    lead_intelligence). Se enriquece con el lead del CRM (contacto, agente,
    estado, propiedad vía ``lead_properties``) y si la visita ya quedó
    registrada (``resolve_visits_for_leads``).
    """
    start = datetime.combine(date_from, dt_time.min)
    end = datetime.combine(date_to, dt_time.max)
    qs = (
        LeadConversationAssessment.objects.using("default")
        .filter(
            visit_intent_status=status,
            analyzed_at__gte=start,
            analyzed_at__lte=end,
        )
        .order_by("-analyzed_at")
    )
    # Último assessment por lead (misma versión del motor).
    by_lead = {}
    for assessment in qs:
        by_lead.setdefault(assessment.source_lead_id, assessment)
    lead_ids = list(by_lead.keys())
    if not lead_ids:
        return []

    placeholders = ", ".join(["%s"] * len(lead_ids))
    with connections["propifai"].cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                l.id,
                COALESCE(l.date_entry, l.created_at) AS entered_at,
                l.assigned_to_id AS agent_id,
                c.first_name, c.last_name, c.phone,
                COALESCE(ls.name, 'Sin estado') AS status_name,
                COALESCE(
                    NULLIF(LTRIM(RTRIM(CONCAT(u.first_name, ' ', u.last_name))), ''),
                    u.username, 'Sin asignar'
                ) AS agent_name,
                lp.property_id,
                p.code AS property_code,
                p.title AS property_title
            FROM dbo.lead l
            LEFT JOIN dbo.contact c ON c.id = l.contact_id
            LEFT JOIN dbo.[user] u ON u.id = l.assigned_to_id
            LEFT JOIN dbo.lead_status ls ON ls.id = l.lead_status_id
            LEFT JOIN dbo.lead_properties lp ON lp.lead_id = l.id
            LEFT JOIN dbo.property p ON p.id = lp.property_id
            WHERE l.id IN ({placeholders})
            """,
            lead_ids,
        )
        rows = _dict_rows(cursor)
    row_by_lead = {int(r["id"]): r for r in rows}

    visit_pairs = {
        int(row["resolved_lead_id"])
        for row in resolve_visits_for_leads(lead_ids, persist=False)
        if row.get("resolved_lead_id") is not None
    }

    items = []
    for lead_id in lead_ids:
        assessment = by_lead[lead_id]
        row = row_by_lead.get(int(lead_id), {})
        if (
            agent_id
            and row.get("agent_id") is not None
            and int(row["agent_id"]) != int(agent_id)
        ):
            continue
        evidence = assessment.visit_intent_evidence or []
        visit_intent_at = (
            evidence[0].get("timestamp")
            if evidence and evidence[0].get("timestamp")
            else (
                assessment.analyzed_at.isoformat()
                if assessment.analyzed_at
                else None
            )
        )
        contact = " ".join(
            part
            for part in (
                str(row.get("first_name") or ""),
                str(row.get("last_name") or ""),
            )
            if part.strip()
        )
        items.append(
            {
                "lead_id": int(lead_id),
                "contact_name": contact,
                "phone": str(row.get("phone") or ""),
                "agent_id": row.get("agent_id"),
                "agent_name": str(row.get("agent_name") or ""),
                "status_name": str(row.get("status_name") or ""),
                "entered_at": row.get("entered_at"),
                "visit_intent_status": assessment.visit_intent_status,
                "visit_intent_confidence": float(assessment.visit_intent_confidence),
                "visit_intent_at": visit_intent_at,
                "visit_intent_evidence": evidence,
                "property_id": row.get("property_id"),
                "property_code": str(row.get("property_code") or ""),
                "property_title": str(row.get("property_title") or ""),
                "visit_registered": int(lead_id) in visit_pairs,
            }
        )
    items.sort(key=lambda item: item["visit_intent_at"] or "", reverse=True)
    return items[:limit]


@analytics_access_required
@require_GET
def visit_intent_api(request):
    """Leads con intención de visita confirmada por la IA (consumo del CRM).

    Params: ``from``/``to`` (periodo, filtra por ``analyzed_at``), ``agent``
    (id de agente asignado), ``status`` (default ``confirmed``), ``limit``.
    Auth: header ``X-Analytics-API-Key`` o sesión de gerencia.
    """
    date_from, date_to, _ = _parameters(request)
    status = request.GET.get("status", "confirmed")
    if status not in {"confirmed", "ambiguous", "not_confirmed"}:
        status = "confirmed"
    agent_id = request.GET.get("agent") or None
    try:
        limit = int(request.GET.get("limit") or 100)
    except (TypeError, ValueError):
        limit = 100
    limit = max(1, min(limit, 500))
    items = get_visit_intent_leads(
        date_from, date_to, status=status, agent_id=agent_id, limit=limit
    )
    return JsonResponse(
        {
            "generated_at": timezone.now().isoformat(),
            "date_from": str(date_from),
            "date_to": str(date_to),
            "status": status,
            "count": len(items),
            "items": items,
        }
    )
