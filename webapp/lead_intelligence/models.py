from django.conf import settings
from django.db import models


class AnalysisRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "En ejecución"
        COMPLETED = "completed", "Completado"
        FAILED = "failed", "Fallido"

    class RunType(models.TextChoices):
        INCREMENTAL = "incremental", "Incremental"
        DAILY = "daily", "Diario"
        MANUAL = "manual", "Manual"

    run_type = models.CharField(max_length=20, choices=RunType.choices)
    status = models.CharField(max_length=20, choices=Status.choices)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    leads_analyzed = models.PositiveIntegerField(default=0)
    diagnoses_created = models.PositiveIntegerField(default=0)
    actions_created = models.PositiveIntegerField(default=0)
    rules_version = models.CharField(max_length=40, default="v1")
    model_version = models.CharField(max_length=80, blank=True)
    error_summary = models.TextField(blank=True)

    class Meta:
        db_table = "prometeo_analysis_run"
        ordering = ["-started_at"]


class LeadDiagnosis(models.Model):
    class Severity(models.TextChoices):
        CRITICAL = "critical", "Crítica"
        HIGH = "high", "Alta"
        MEDIUM = "medium", "Media"
        LOW = "low", "Baja"

    run = models.ForeignKey(
        AnalysisRun, on_delete=models.CASCADE, related_name="diagnoses"
    )
    source_lead_id = models.BigIntegerField(db_index=True)
    diagnosis_code = models.CharField(max_length=60, db_index=True)
    severity = models.CharField(max_length=10, choices=Severity.choices, db_index=True)
    reason = models.CharField(max_length=500)
    evidence = models.JSONField(default=dict)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=1)
    detected_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "prometeo_lead_diagnosis"
        indexes = [
            models.Index(
                fields=["source_lead_id", "is_active"],
                name="pli_diag_lead_active",
            ),
            models.Index(
                fields=["severity", "detected_at"],
                name="pli_diag_sev_date",
            ),
        ]


class RecommendedAction(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        COMPLETED = "completed", "Completada"
        DISMISSED = "dismissed", "Descartada"
        EXPIRED = "expired", "Vencida"

    diagnosis = models.ForeignKey(
        LeadDiagnosis, on_delete=models.CASCADE, related_name="actions"
    )
    source_lead_id = models.BigIntegerField(db_index=True)
    source_assigned_user_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    action_type = models.CharField(max_length=60)
    priority = models.CharField(
        max_length=10, choices=LeadDiagnosis.Severity.choices, db_index=True
    )
    title = models.CharField(max_length=180)
    reason = models.CharField(max_length=500)
    suggested_channel = models.CharField(max_length=20, blank=True)
    suggested_template_code = models.CharField(max_length=100, blank=True)
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by_source_user_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "prometeo_recommended_action"
        indexes = [
            models.Index(
                fields=["source_assigned_user_id", "status", "due_at"],
                name="pli_action_agent_due",
            ),
        ]


class ActionOutcome(models.Model):
    action = models.ForeignKey(
        RecommendedAction, on_delete=models.CASCADE, related_name="outcomes"
    )
    outcome_code = models.CharField(max_length=60)
    notes = models.TextField(blank=True)
    next_contact_at = models.DateTimeField(null=True, blank=True)
    source_user_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prometeo_action_outcome"
        ordering = ["-created_at"]


class LeadMilestone(models.Model):
    source_lead_id = models.BigIntegerField(db_index=True)
    milestone_code = models.CharField(max_length=50, db_index=True)
    first_reached_at = models.DateTimeField(db_index=True)
    source_type = models.CharField(max_length=30)
    source_reference_id = models.CharField(max_length=100, blank=True)
    rules_version = models.CharField(max_length=40, default="v1")
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=1)

    class Meta:
        db_table = "prometeo_lead_milestone"
        constraints = [
            models.UniqueConstraint(
                fields=["source_lead_id", "milestone_code", "rules_version"],
                name="pli_unique_milestone_version",
            )
        ]

