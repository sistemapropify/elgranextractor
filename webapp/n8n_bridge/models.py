"""Persistencia del respondedor nocturno de WhatsApp."""

import uuid

from django.conf import settings
from django.db import models


def default_property_bot_types():
    return ["casa", "departamento", "terreno", "local_comercial"]

class PropertyBotConfiguration(models.Model):
    """Configuración operacional singleton del respondedor inicial."""

    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    enabled = models.BooleanField(default=False)
    start_time = models.TimeField(default="00:00")
    end_time = models.TimeField(default="05:00")
    timezone_name = models.CharField(max_length=64, default="America/Lima")
    require_external_conversation_id = models.BooleanField(default=True)
    enabled_property_types = models.JSONField(
        default=default_property_bot_types
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="property_bot_config_updates",
    )

    class Meta:
        db_table = "n8n_property_bot_configuration"


class PropertyBotInitialResponse(models.Model):
    """Decisión idempotente y auditable para el primer mensaje de un hilo."""

    ACTION_CHOICES = [
        ("respond_once", "Responder una vez"),
        ("ignore", "Ignorar"),
    ]
    REVIEW_CHOICES = [
        ("not_required", "No requerida"),
        ("pending", "Pendiente"),
        ("confirmed_ok", "Correcta"),
        ("confirmed_error", "Error"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message_id = models.CharField(max_length=255, unique=True)
    external_conversation_id = models.CharField(max_length=255, db_index=True)
    conversation_property_key = models.CharField(max_length=512, unique=True)
    phone_hash = models.CharField(max_length=64, db_index=True)
    phone_last4 = models.CharField(max_length=4, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    contact_name = models.CharField(max_length=255, blank=True, default="")
    property_id = models.BigIntegerField(null=True, blank=True)
    property_code = models.CharField(max_length=50, blank=True, default="", db_index=True)
    property_type = models.CharField(max_length=50, blank=True, default="")
    incoming_text = models.TextField(blank=True, default="")
    response_text = models.TextField(blank=True, default="")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default="ignore", db_index=True)
    reason_code = models.CharField(max_length=64, db_index=True)
    evidence = models.JSONField(default=dict, blank=True)
    bot_enabled = models.BooleanField(default=False)
    schedule_snapshot = models.JSONField(default=dict, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    review_status = models.CharField(
        max_length=32,
        choices=REVIEW_CHOICES,
        default="not_required",
        db_index=True,
    )
    review_note = models.TextField(blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="property_bot_reviews",
    )
    episode_id = models.UUIDField(null=True, blank=True)
    error_type = models.CharField(max_length=100, blank=True, default="")
    error_preview = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "n8n_property_bot_initial_response"
        indexes = [
            models.Index(fields=["received_at", "action"]),
            models.Index(fields=["reason_code", "received_at"]),
        ]


class PropertyBotControlAudit(models.Model):
    """Historial de cambios operacionales del bot."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=50, db_index=True)
    previous_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="property_bot_control_actions",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "n8n_property_bot_control_audit"
