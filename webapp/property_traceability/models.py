from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PropertyWorkflow(models.Model):
    """Workflow local enlazado por ID a dbo.property en dbpropify_be."""

    property_id = models.BigIntegerField(unique=True, db_index=True)
    current_stage = models.CharField(max_length=40, default="draft", db_index=True)
    general_status = models.CharField(max_length=30, default="draft", db_index=True)
    sellability_score = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "property_traceability_workflow"
        ordering = ("-updated_at",)


class StageExecution(models.Model):
    STATUS_CHOICES = (
        ("completed", "Completada"),
        ("in_progress", "En progreso"),
        ("pending", "Pendiente"),
        ("blocked", "Bloqueada"),
        ("overdue", "Atrasada"),
        ("rejected", "Rechazada"),
        ("paused", "Pausada"),
        ("disabled", "No habilitada"),
    )

    workflow = models.ForeignKey(PropertyWorkflow, on_delete=models.CASCADE, related_name="stages")
    stage_key = models.CharField(max_length=40)
    stage_order = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="disabled", db_index=True)
    area = models.CharField(max_length=60, blank=True, default="")
    responsible_id = models.BigIntegerField(null=True, blank=True)
    progress = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)
    blocked_reason = models.TextField(blank=True, default="")
    active_seconds = models.PositiveBigIntegerField(default=0)
    blocked_seconds = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "property_traceability_stage"
        ordering = ("stage_order",)
        constraints = [models.UniqueConstraint(fields=("workflow", "stage_key"), name="uq_trace_stage_workflow_key")]
        indexes = [models.Index(fields=("status", "due_at"), name="trace_stage_status_due_idx")]


class StageRequirement(models.Model):
    STATUS_CHOICES = (
        ("missing", "Falta"),
        ("requested", "Solicitado"),
        ("received", "Recibido"),
        ("observed", "Observado"),
        ("approved", "Aprobado"),
    )

    stage = models.ForeignKey(StageExecution, on_delete=models.CASCADE, related_name="requirements")
    code = models.CharField(max_length=80)
    label = models.CharField(max_length=160)
    is_mandatory = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="missing")
    requested_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    evidence_url = models.URLField(max_length=1000, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "property_traceability_requirement"
        constraints = [models.UniqueConstraint(fields=("stage", "code"), name="uq_trace_requirement_stage_code")]


class ParallelTask(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pendiente"),
        ("in_progress", "En progreso"),
        ("completed", "Completada"),
        ("paused", "Pausada"),
        ("blocked", "Bloqueada"),
    )

    workflow = models.ForeignKey(PropertyWorkflow, on_delete=models.CASCADE, related_name="parallel_tasks")
    anchor_stage_key = models.CharField(max_length=40)
    code = models.CharField(max_length=80)
    label = models.CharField(max_length=160)
    area = models.CharField(max_length=60, blank=True, default="")
    responsible_id = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "property_traceability_parallel_task"
        constraints = [models.UniqueConstraint(fields=("workflow", "code"), name="uq_trace_parallel_workflow_code")]


class WorkflowEvent(models.Model):
    """Registro inmutable de auditoría y fuente de métricas temporales."""

    workflow = models.ForeignKey(PropertyWorkflow, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=40)
    from_stage = models.CharField(max_length=40, blank=True, default="")
    to_stage = models.CharField(max_length=40, blank=True, default="")
    actor_id = models.BigIntegerField(null=True, blank=True)
    area = models.CharField(max_length=60, blank=True, default="")
    reason = models.TextField(blank=True, default="")
    occurred_at = models.DateTimeField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "property_traceability_event"
        ordering = ("occurred_at", "id")
        indexes = [models.Index(fields=("workflow", "occurred_at"), name="trace_event_workflow_at_idx")]

