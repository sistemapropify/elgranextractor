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
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
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


class PlantillaMensaje(models.Model):
    """Plantilla de mensaje de seguimiento/remarketing.

    El dashboard de remarketing analiza TODAS las plantillas activas
    (``activa=True``): cada mensaje saliente se compara contra la
    ``frase_condicion`` (normalizada) o la ``regex_condicion`` de cada
    plantilla para decidir a qué plantilla pertenece. ``sql_hint`` es un
    patrón SQL ``LIKE`` amplio usado solo para prefiltrar
    ``dbo.lead.chat_history`` en el CRM.
    """

    codigo = models.CharField(max_length=100, unique=True)
    titulo = models.CharField(max_length=200, verbose_name="Título de la plantilla")
    cuerpo = models.TextField(
        blank=True,
        default="",
        help_text="Texto literal de la plantilla (solo informativo/visual).",
    )
    orden = models.PositiveSmallIntegerField(
        default=1, verbose_name="Orden / intento", help_text="Ej.: 1, 2, 3…"
    )
    frase_condicion = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Condición (frase)",
        help_text="Frase que el mensaje debe contener para contarse. Se normaliza (sin mayúsculas/signos). Ej.: pudiste leer mi mensaje",
    )
    regex_condicion = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Condición (regex, opcional)",
        help_text="Patrón regex opcional, más preciso que la frase.",
    )
    sql_hint = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Patrón SQL LIKE",
        help_text="Patrón LIKE amplio para prefiltrar el CRM. Ej.: %Pudiste leer mi mensaje%",
    )
    activa = models.BooleanField(
        default=True,
        help_text="Solo las plantillas activas se autorizan en el análisis.",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prometeo_plantilla_mensaje"
        ordering = ["orden", "id"]

    def __str__(self):
        return self.titulo


class RemarketingCampaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        ACTIVE = 'active', 'Activa'
        PAUSED = 'paused', 'Pausada'

    name = models.CharField(max_length=160)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    revision = models.PositiveIntegerField(default=1)
    # Positive allowlists: a CRM status/channel that is unknown never opts in.
    allowed_statuses = models.JSONField(default=list)
    allowed_channels = models.JSONField(default=list)
    agent_ids = models.JSONField(default=list, blank=True)
    contact_sender = models.CharField(max_length=10, default='agent', choices=[('agent', 'Humano'), ('any', 'Humano o bot')])
    daily_limit = models.PositiveIntegerField(default=100)
    hourly_limit = models.PositiveIntegerField(default=20)
    contact_limit = models.PositiveIntegerField(default=3)
    min_gap_minutes = models.PositiveIntegerField(default=60)
    window_margin_minutes = models.PositiveIntegerField(default=10)
    start_hour = models.PositiveSmallIntegerField(default=9)
    end_hour = models.PositiveSmallIntegerField(default=18)
    weekdays = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class RemarketingStep(models.Model):
    campaign = models.ForeignKey(RemarketingCampaign, on_delete=models.CASCADE, related_name='steps')
    title = models.CharField(max_length=160)
    body = models.TextField()
    delay_minutes = models.PositiveIntegerField()

    class Meta:
        ordering = ['delay_minutes', 'pk']
        constraints = [models.UniqueConstraint(fields=['campaign', 'delay_minutes'], name='rm_unique_step_delay')]


class RemarketingEnrollment(models.Model):
    campaign = models.ForeignKey(RemarketingCampaign, on_delete=models.PROTECT, related_name='enrollments')
    revision = models.PositiveIntegerField()
    source_lead_id = models.BigIntegerField(db_index=True)
    contact_key = models.CharField(max_length=128, db_index=True)
    episode_key = models.CharField(max_length=64, unique=True)
    anchor_at = models.DateTimeField()
    last_inbound_at = models.DateTimeField()
    # These snapshots are immutable, including policy and rendered messages.
    policy = models.JSONField(default=dict)
    context = models.JSONField(default=dict)
    status = models.CharField(max_length=16, default='active', db_index=True)
    stop_reason = models.CharField(max_length=200, blank=True)
    response_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class RemarketingDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Programado'
        SENDING = 'sending', 'Enviando'
        ACCEPTED = 'accepted', 'Aceptado por proveedor'
        SENT = 'sent', 'Enviado'
        DELIVERED = 'delivered', 'Entregado'
        FAILED = 'failed', 'Fallido'
        UNCERTAIN = 'uncertain', 'Resultado incierto'
        SKIPPED = 'skipped', 'Omitido'
        CANCELLED = 'cancelled', 'Cancelado'

    enrollment = models.ForeignKey(RemarketingEnrollment, on_delete=models.PROTECT, related_name='deliveries')
    position = models.PositiveIntegerField()
    title = models.CharField(max_length=160)
    body = models.TextField()
    due_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    idempotency_key = models.UUIDField(unique=True)
    attempted_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    response_at = models.DateTimeField(null=True, blank=True)
    provider_message_id = models.CharField(max_length=200, blank=True)
    reason = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ['due_at', 'pk']
        constraints = [models.UniqueConstraint(fields=['enrollment', 'position'], name='rm_unique_delivery_step')]


class RemarketingRuntime(models.Model):
    """Singleton mutex for quota reservations, and persistent source scan cursor."""
    scan_after_id = models.BigIntegerField(default=0)


class LeadControlPolicy(models.Model):
    name = models.CharField(max_length=120, default='Control comercial')
    active_statuses = models.JSONField(default=list)
    closed_statuses = models.JSONField(default=list)
    start_hour = models.PositiveSmallIntegerField(default=9)
    end_hour = models.PositiveSmallIntegerField(default=18)
    weekdays = models.JSONField(default=list)
    holidays = models.JSONField(default=list, blank=True)
    first_minutes = models.PositiveIntegerField(default=5)
    first_supervisor = models.PositiveIntegerField(default=15)
    first_manager = models.PositiveIntegerField(default=30)
    reply_minutes = models.PositiveIntegerField(default=15)
    reply_supervisor = models.PositiveIntegerField(default=30)
    reply_manager = models.PositiveIntegerField(default=60)
    visit_minutes = models.PositiveIntegerField(default=10)
    visit_supervisor = models.PositiveIntegerField(default=20)
    visit_manager = models.PositiveIntegerField(default=30)
    assignment_minutes = models.PositiveIntegerField(default=2)
    followup_hours = models.PositiveIntegerField(default=24)
    stale_minutes = models.PositiveIntegerField(default=15)
    digest_hour = models.PositiveSmallIntegerField(default=17)
    revision = models.PositiveIntegerField(default=1)
    scan_after_id = models.BigIntegerField(default=0)
    scan_lease_token = models.CharField(max_length=32, blank=True)
    scan_lease_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class LeadControlMember(models.Model):
    name = models.CharField(max_length=150)
    identity_type = models.CharField(max_length=15, choices=[('django', 'Django'), ('intelligence', 'Prometeo'), ('propify', 'Propify / APK')])
    identity_id = models.CharField(max_length=100)
    mobile_identity_id = models.CharField(max_length=100, blank=True)
    source_user_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    role = models.CharField(max_length=15, choices=[('agent', 'Agente'), ('supervisor', 'Supervisor'), ('manager', 'Gerencia')], default='agent')
    email = models.EmailField(blank=True)
    supervisor = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='team')
    active = models.BooleanField(default=True)
    away_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['identity_type', 'identity_id'], name='lc_unique_identity')]
        ordering = ['name']

    def __str__(self):
        return self.name


class LeadControlState(models.Model):
    source_lead_id = models.BigIntegerField(unique=True)
    crm_agent_id = models.BigIntegerField(null=True, blank=True)
    owner_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    name = models.CharField(max_length=200, blank=True)
    property_title = models.CharField(max_length=300, blank=True)
    status_name = models.CharField(max_length=100, blank=True)
    active = models.BooleanField(default=True, db_index=True)
    quality = models.CharField(max_length=20, default='unknown')
    snapshot = models.JSONField(default=dict)
    observed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=240, blank=True)
    entered_at = models.DateTimeField(null=True, blank=True)
    assignment_since = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class LeadObligation(models.Model):
    lead = models.ForeignKey(LeadControlState, on_delete=models.PROTECT, related_name='obligations')
    action = models.OneToOneField(RecommendedAction, on_delete=models.PROTECT, related_name='control')
    event_key = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=30, db_index=True)
    started_at = models.DateTimeField()
    original_due_at = models.DateTimeField()
    supervisor_at = models.DateTimeField()
    manager_at = models.DateTimeField()
    calendar = models.JSONField(default=dict)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_evidence = models.JSONField(default=dict)


class LeadControlEvent(models.Model):
    lead = models.ForeignKey(LeadControlState, on_delete=models.PROTECT, related_name='events')
    obligation = models.ForeignKey(LeadObligation, on_delete=models.PROTECT, related_name='events', null=True, blank=True)
    kind = models.CharField(max_length=40)
    actor = models.CharField(max_length=140, default='system')
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']


class LeadControlNotice(models.Model):
    obligation = models.ForeignKey(LeadObligation, on_delete=models.PROTECT, related_name='notices')
    recipient = models.ForeignKey(LeadControlMember, null=True, blank=True, on_delete=models.PROTECT, related_name='notices')
    dedupe_key = models.CharField(max_length=160, unique=True)
    level = models.CharField(max_length=20)
    channel = models.CharField(max_length=15)
    destination = models.CharField(max_length=512, blank=True)
    device_id = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default='pending', db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    provider_id = models.CharField(max_length=250, blank=True)
    last_error = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)


class LeadControlDigest(models.Model):
    recipient = models.ForeignKey(LeadControlMember, on_delete=models.PROTECT, related_name='digests')
    day = models.DateField()
    payload = models.JSONField(default=dict)
    email_status = models.CharField(max_length=20, default='pending')
    emailed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['recipient', 'day'], name='lc_unique_daily_digest')]
        ordering = ['-day', '-id']
