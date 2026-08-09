"""Modelos del motor de respuestas IA (few-shot + RAG) y su sandbox.

Todo vive en la BD ``default`` (``propiextractor``), igual que ``lead_intelligence``.
El CRM (``propifai``) nunca se escribe desde este módulo: solo lectura SELECT.
"""

from django.conf import settings
from django.db import models


class CuratedExample(models.Model):
    """Banco de ejemplos few-shot, alimentado desde evaluaciones ya existentes."""

    class IntentCategory(models.TextChoices):
        PRECIO = "precio", "Precio"
        UBICACION = "ubicacion", "Ubicación"
        VISITA = "visita", "Visita"
        FINANCIAMIENTO = "financiamiento", "Financiamiento"
        OBJECION_PRECIO = "objecion_precio", "Objeción de precio"
        DISPONIBILIDAD = "disponibilidad", "Disponibilidad"
        OTRO = "otro", "Otro"

    source_lead_id = models.BigIntegerField(db_index=True)
    source_assessment = models.ForeignKey(
        "lead_intelligence.LeadConversationAssessment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="curated_examples",
    )
    intent_category = models.CharField(
        max_length=24, choices=IntentCategory.choices, db_index=True
    )
    client_message = models.TextField(blank=True, default="")
    agent_response = models.TextField(blank=True, default="")
    quality_scores = models.JSONField(default=dict, blank=True)
    approved = models.BooleanField(default=False, db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="curated_example_approvals",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prometeo_curated_example"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["intent_category", "active", "approved"],
                name="curated_cat_active_approved",
            )
        ]

    def __str__(self):
        return (
            f"[{self.intent_category}] lead#{self.source_lead_id} "
            f"{'aprobado' if self.approved else 'pendiente'}"
        )


class BusinessRule(models.Model):
    """Regla de negocio auditable inyectada en el prompt del motor."""

    class Category(models.TextChoices):
        PROHIBICION = "prohibicion", "Prohibición"
        TONO = "tono", "Tono"
        ESCALAMIENTO = "escalamiento", "Escalamiento"

    rule_text = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices)
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prometeo_business_rule"
        ordering = ["category", "id"]

    def __str__(self):
        return f"{self.category}: {self.rule_text[:80]}"


class BotResponseDraft(models.Model):
    """Borrador de respuesta generado por el motor (equivale al assessment de generación)."""

    class Mode(models.TextChoices):
        SANDBOX = "sandbox", "Sandbox offline"
        SHADOW_LIVE = "shadow_live", "Shadow en vivo"
        PRODUCTION = "production", "Producción"

    source_lead_id = models.BigIntegerField(db_index=True)
    client_message = models.TextField(blank=True, default="")
    intent_category = models.CharField(
        max_length=24,
        choices=CuratedExample.IntentCategory.choices,
        blank=True,
        default="",
        db_index=True,
    )
    # Prompt completo usado (reglas + ejemplos + datos SQL en ese momento).
    prompt_snapshot = models.JSONField(default=dict, blank=True)
    generated_response = models.TextField(blank=True, default="")
    property_data_used = models.JSONField(default=list, blank=True)
    mode = models.CharField(max_length=20, choices=Mode.choices, db_index=True)
    model_version = models.CharField(max_length=80, blank=True, default="")
    trace_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Guardrails deterministas automáticos (spec §7), auditables en el dashboard.
    auto_escalation = models.BooleanField(default=False, db_index=True)
    auto_hallucination = models.BooleanField(default=False, db_index=True)
    auto_discount = models.BooleanField(default=False, db_index=True)
    blocked_reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "prometeo_bot_response_draft"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["mode", "created_at"], name="draft_mode_date"),
            models.Index(
                fields=["source_lead_id", "created_at"], name="draft_lead_date"
            ),
        ]

    def __str__(self):
        return (
            f"draft#{self.pk} lead#{self.source_lead_id} "
            f"({self.mode} · {self.intent_category or 'sin categoría'})"
        )


class BotResponseEvaluation(models.Model):
    """Revisión humana de un borrador (mismo patrón que LeadConversationReview)."""

    class Verdict(models.TextChoices):
        CORRECT = "correct", "Correcto"
        INCORRECT = "incorrect", "Incorrecto"
        ACCEPTABLE = "acceptable_with_adjustment", "Aceptable con ajuste"

    draft = models.ForeignKey(
        BotResponseDraft,
        on_delete=models.CASCADE,
        related_name="evaluations",
    )
    verdict = models.CharField(max_length=30, choices=Verdict.choices)
    hallucination_flag = models.BooleanField(default=False)
    tone_flag = models.BooleanField(default=False)
    would_send = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bot_response_evaluations",
    )
    reviewed_at = models.DateTimeField(auto_now=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "prometeo_bot_response_evaluation"
        ordering = ["-reviewed_at"]
        indexes = [
            models.Index(fields=["verdict", "reviewed_at"], name="eval_verdict_date")
        ]

    def __str__(self):
        return f"eval#{self.pk} → {self.verdict} (draft#{self.draft_id})"


class MotorAIControl(models.Model):
    """Interruptor persistente del Motor IA (BD ``default``).

    Permite activar/desactivar el shadow_live desde el dashboard sin depender
    solo de variables de entorno ni reiniciar el proceso. Es un singleton: la
    primera fila es la vigente. ``shadow_mode_enabled()`` la consulta y, si no
    existe, cae al valor de la variable ``RESPONSE_INTELLIGENCE_SHADOW``.
    """

    shadow_live_enabled = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="motor_ai_controls",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prometeo_motor_ai_control"

    def __str__(self):
        return f"MotorIA shadow_live={'ON' if self.shadow_live_enabled else 'OFF'}"
