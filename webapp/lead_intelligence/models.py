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
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    leads_total = models.PositiveIntegerField(default=0)
    leads_analyzed = models.PositiveIntegerField(default=0)
    leads_skipped = models.PositiveIntegerField(default=0)
    leads_failed = models.PositiveIntegerField(default=0)
    diagnoses_created = models.PositiveIntegerField(default=0)
    actions_created = models.PositiveIntegerField(default=0)
    rules_version = models.CharField(max_length=40, default="v1")
    model_version = models.CharField(max_length=80, blank=True)
    error_summary = models.TextField(blank=True)

    class Meta:
        db_table = "prometeo_analysis_run"
        ordering = ["-started_at"]


class AnalysisRunStep(models.Model):
    """Paso del log en vivo de una ejecución (terminal de progreso)."""

    run = models.ForeignKey(
        AnalysisRun, on_delete=models.CASCADE, related_name="steps"
    )
    lead_id = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default="processed")
    message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prometeo_analysis_run_step"
        ordering = ["created_at", "id"]


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


class LeadConversationAssessment(models.Model):
    class Decision(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmado"
        NOT_CONFIRMED = "not_confirmed", "No confirmado"
        AMBIGUOUS = "ambiguous", "Ambiguo"

    class AttentionDecision(models.TextChoices):
        ADEQUATE = "adequate", "Adecuada"
        PARTIAL = "partial", "Parcial"
        INADEQUATE = "inadequate", "Inadecuada"
        NOT_APPLICABLE = "not_applicable", "No aplica"
        AMBIGUOUS = "ambiguous", "Ambigua"

    source_lead_id = models.BigIntegerField(db_index=True)
    history_hash = models.CharField(max_length=64, db_index=True)
    analysis_version = models.CharField(max_length=40, default="context-v2")
    qualified_status = models.CharField(max_length=20, choices=Decision.choices)
    visit_intent_status = models.CharField(max_length=20, choices=Decision.choices)
    qualified_confidence = models.DecimalField(max_digits=5, decimal_places=4)
    visit_intent_confidence = models.DecimalField(max_digits=5, decimal_places=4)
    qualified_evidence = models.JSONField(default=list)
    visit_intent_evidence = models.JSONField(default=list)
    reason = models.TextField(blank=True)
    first_response_status = models.CharField(
        max_length=20,
        choices=AttentionDecision.choices,
        null=True,
        blank=True,
    )
    first_response_confidence = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True
    )
    relevance_score = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True
    )
    coverage_score = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True
    )
    directness_score = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True
    )
    personalization_score = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True
    )
    lead_request_items = models.JSONField(default=list)
    answered_request_items = models.JSONField(default=list)
    unanswered_request_items = models.JSONField(default=list)
    first_response_evidence = models.JSONField(default=list)
    attention_reason = models.TextField(blank=True)
    model_version = models.CharField(max_length=80)
    analyzed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "prometeo_lead_conversation_assessment"
        ordering = ["-analyzed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_lead_id", "history_hash", "analysis_version"],
                name="pli_unique_conversation_assessment",
            )
        ]
        indexes = [
            models.Index(
                fields=["source_lead_id", "analysis_version", "analyzed_at"],
                name="pli_assess_lead_ver_date",
            )
        ]


class LeadConversationReview(models.Model):
    class Stage(models.TextChoices):
        QUALIFIED = "qualified", "Calificación"
        VISIT_INTENT = "visit_intent", "Intención de visita"
        FIRST_RESPONSE = "first_response", "Primera respuesta"

    class Verdict(models.TextChoices):
        CORRECT = "correct", "Correcto"
        INCORRECT = "incorrect", "Incorrecto"
        UNSURE = "unsure", "Requiere discusión"

    source_lead_id = models.BigIntegerField(db_index=True)
    history_hash = models.CharField(max_length=64, db_index=True)
    analysis_version = models.CharField(max_length=40, db_index=True)
    stage = models.CharField(max_length=20, choices=Stage.choices)
    ai_value = models.CharField(max_length=30)
    human_value = models.CharField(max_length=30)
    verdict = models.CharField(max_length=15, choices=Verdict.choices)
    notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_conversation_reviews",
    )
    reviewed_at = models.DateTimeField(auto_now=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prometeo_lead_conversation_review"
        ordering = ["-reviewed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source_lead_id",
                    "history_hash",
                    "analysis_version",
                    "stage",
                ],
                name="pli_unique_conversation_review",
            )
        ]
        indexes = [
            models.Index(
                fields=["analysis_version", "stage", "verdict"],
                name="pli_review_ver_stage_result",
            )
        ]


class LeadEventResolution(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmado"
        MANUAL_REVIEW = "manual_review", "Revisión manual"
        UNRESOLVED = "unresolved", "Sin resolver"

    source_event_id = models.BigIntegerField(db_index=True)
    source_lead_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    source_contact_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    source_property_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    event_created_at = models.DateTimeField(null=True, blank=True)
    event_scheduled_at = models.DateTimeField(null=True, blank=True)
    resolution_method = models.CharField(max_length=40, db_index=True)
    resolution_status = models.CharField(
        max_length=20,
        choices=Status.choices,
        db_index=True,
    )
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    candidate_count = models.PositiveIntegerField(default=0)
    evidence = models.JSONField(default=dict)
    resolver_version = models.CharField(max_length=40, db_index=True)
    resolved_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "prometeo_lead_event_resolution"
        ordering = ["-resolved_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_event_id", "resolver_version"],
                name="pli_unique_event_resolution_version",
            )
        ]
        indexes = [
            models.Index(
                fields=["source_lead_id", "resolution_status"],
                name="pli_event_lead_status",
            ),
            models.Index(
                fields=["resolver_version", "resolution_status"],
                name="pli_event_ver_status",
            ),
        ]
