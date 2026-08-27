from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .constants import DEFAULT_REQUIREMENTS, STAGES, STAGE_BY_KEY, STAGE_GATES
from .models import PropertyWorkflow, StageExecution, StageRequirement, WorkflowEvent


def ensure_workflow(property_id, *, actor_id=None):
    """Crea el flujo local inicial sin escribir en dbpropify_be."""
    with transaction.atomic():
        workflow, created = PropertyWorkflow.objects.select_for_update().get_or_create(property_id=property_id)
        if created:
            now = timezone.now()
            executions = []
            for definition in STAGES:
                status = "completed" if definition.key == "captation" else "in_progress" if definition.key == "draft" else "disabled"
                executions.append(StageExecution(
                    workflow=workflow,
                    stage_key=definition.key,
                    stage_order=definition.order,
                    status=status,
                    area=definition.area,
                    progress=100 if status == "completed" else 0,
                    started_at=now if status in {"completed", "in_progress"} else None,
                    completed_at=now if status == "completed" else None,
                    due_at=now + timedelta(hours=definition.sla_hours) if status == "in_progress" and definition.sla_hours else None,
                ))
            StageExecution.objects.bulk_create(executions)
            created_stages = {item.stage_key: item for item in workflow.stages.all()}
            requirements = []
            for stage_key, definitions in DEFAULT_REQUIREMENTS.items():
                for code, label, mandatory in definitions:
                    requirements.append(StageRequirement(
                        stage=created_stages[stage_key], code=code, label=label, is_mandatory=mandatory,
                    ))
            StageRequirement.objects.bulk_create(requirements)
            WorkflowEvent.objects.create(
                workflow=workflow,
                event_type="workflow_created",
                to_stage="draft",
                actor_id=actor_id,
                area="Comercial",
                occurred_at=now,
            )
        return workflow


def gate_state(workflow, target_stage):
    required_codes = STAGE_GATES.get(target_stage, ())
    if not required_codes:
        return True, []
    approved = set(StageRequirement.objects.filter(
        stage__workflow=workflow,
        code__in=required_codes,
        status="approved",
    ).values_list("code", flat=True))
    documentation = StageRequirement.objects.filter(stage__workflow=workflow, stage__stage_key="documentation", is_mandatory=True)
    if documentation.exists() and not documentation.exclude(status="approved").exists():
        approved.add("mandatory_documents_complete")
    marketing = StageRequirement.objects.filter(stage__workflow=workflow, stage__stage_key="marketing", is_mandatory=True)
    if marketing.exists() and not marketing.exclude(status="approved").exists():
        approved.add("marketing_material_approved")
    if workflow.stages.filter(stage_key="accepted_offer", status="completed").exists():
        approved.add("accepted_offer_registered")
    missing = [code for code in required_codes if code not in approved]
    return not missing, missing


def transition(workflow, target_stage, *, actor_id=None, reason=""):
    """Avanza una etapa respetando las puertas obligatorias."""
    if target_stage not in STAGE_BY_KEY:
        raise ValueError("Etapa desconocida")
    allowed, missing = gate_state(workflow, target_stage)
    if not allowed:
        raise ValueError("Requisitos pendientes: " + ", ".join(missing))
    target = workflow.stages.get(stage_key=target_stage)
    current = workflow.stages.get(stage_key=workflow.current_stage)
    if target.stage_order < current.stage_order and not reason.strip():
        raise ValueError("El motivo es obligatorio para retroceder una etapa")
    now = timezone.now()
    with transaction.atomic():
        if current.status == "in_progress":
            current.status = "completed"
            current.progress = 100
            current.completed_at = now
            current.save(update_fields=("status", "progress", "completed_at", "updated_at"))
        target.status = "in_progress"
        target.started_at = target.started_at or now
        definition = STAGE_BY_KEY[target_stage]
        target.due_at = now + timedelta(hours=definition.sla_hours) if definition.sla_hours else None
        target.save(update_fields=("status", "started_at", "due_at", "updated_at"))
        previous_stage = workflow.current_stage
        workflow.current_stage = target_stage
        workflow.general_status = "closed" if target_stage == "closed" else "draft" if target.stage_order < 7 else "published"
        workflow.save(update_fields=("current_stage", "general_status", "updated_at"))
        WorkflowEvent.objects.create(
            workflow=workflow,
            event_type="stage_transition",
            from_stage=previous_stage,
            to_stage=target_stage,
            actor_id=actor_id,
            area=definition.area,
            reason=reason,
            occurred_at=now,
        )
    return workflow


def duration_hours(stage, now=None):
    if not stage.started_at:
        return 0
    end = stage.completed_at or now or timezone.now()
    seconds = max(0, (end - stage.started_at).total_seconds())
    return round(seconds / 3600, 1)


def stage_progress(stage):
    requirements = list(stage.requirements.all())
    if not requirements:
        return stage.progress
    mandatory = [item for item in requirements if item.is_mandatory]
    scope = mandatory or requirements
    approved = sum(item.status == "approved" for item in scope)
    return round(approved * 100 / len(scope)) if scope else stage.progress
