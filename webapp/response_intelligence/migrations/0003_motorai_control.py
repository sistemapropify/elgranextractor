"""Interruptor persistente del Motor IA (MotorAIControl) para el shadow en vivo.

Permite activar/desactivar el shadow_live desde el dashboard sin variables de
entorno ni reinicio del proceso. Todo en la BD ``default`` (propiextractor).
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("response_intelligence", "0002_guardrails"),
    ]

    operations = [
        migrations.CreateModel(
            name="MotorAIControl",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("shadow_live_enabled", models.BooleanField(default=False)),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="motor_ai_controls",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "prometeo_motor_ai_control",
            },
        ),
    ]
