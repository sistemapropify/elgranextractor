import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import n8n_bridge.models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="PropertyBotConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("singleton_key", models.PositiveSmallIntegerField(default=1, editable=False, unique=True)),
                ("enabled", models.BooleanField(default=False)),
                ("start_time", models.TimeField(default="00:00")),
                ("end_time", models.TimeField(default="05:00")),
                ("timezone_name", models.CharField(default="America/Lima", max_length=64)),
                ("require_external_conversation_id", models.BooleanField(default=True)),
                ("enabled_property_types", models.JSONField(default=n8n_bridge.models.default_property_bot_types)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="property_bot_config_updates", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "n8n_property_bot_configuration"},
        ),
        migrations.CreateModel(
            name="PropertyBotInitialResponse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("message_id", models.CharField(max_length=255, unique=True)),
                ("external_conversation_id", models.CharField(db_index=True, max_length=255)),
                ("conversation_property_key", models.CharField(max_length=512, unique=True)),
                ("phone_hash", models.CharField(db_index=True, max_length=64)),
                ("phone_last4", models.CharField(blank=True, default="", max_length=4)),
                ("property_id", models.BigIntegerField(blank=True, null=True)),
                ("property_code", models.CharField(blank=True, db_index=True, default="", max_length=50)),
                ("property_type", models.CharField(blank=True, default="", max_length=50)),
                ("incoming_text", models.TextField(blank=True, default="")),
                ("response_text", models.TextField(blank=True, default="")),
                ("action", models.CharField(choices=[("respond_once", "Responder una vez"), ("ignore", "Ignorar")], db_index=True, default="ignore", max_length=20)),
                ("reason_code", models.CharField(db_index=True, max_length=64)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("bot_enabled", models.BooleanField(default=False)),
                ("schedule_snapshot", models.JSONField(blank=True, default=dict)),
                ("latency_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("received_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("review_status", models.CharField(choices=[("not_required", "No requerida"), ("pending", "Pendiente"), ("confirmed_ok", "Correcta"), ("confirmed_error", "Error")], db_index=True, default="not_required", max_length=32)),
                ("review_note", models.TextField(blank=True, default="")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("episode_id", models.UUIDField(blank=True, null=True)),
                ("error_type", models.CharField(blank=True, default="", max_length=100)),
                ("error_preview", models.CharField(blank=True, default="", max_length=500)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="property_bot_reviews", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "n8n_property_bot_initial_response"},
        ),
        migrations.CreateModel(
            name="PropertyBotControlAudit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(db_index=True, max_length=50)),
                ("previous_value", models.JSONField(blank=True, default=dict)),
                ("new_value", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="property_bot_control_actions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "n8n_property_bot_control_audit"},
        ),
        migrations.AddIndex(model_name="propertybotinitialresponse", index=models.Index(fields=["received_at", "action"], name="n8n_propert_receive_07fc15_idx")),
        migrations.AddIndex(model_name="propertybotinitialresponse", index=models.Index(fields=["reason_code", "received_at"], name="n8n_propert_reason__4fa0c4_idx")),
    ]
