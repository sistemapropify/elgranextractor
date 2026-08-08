"""Guardrails deterministas automáticos en BotResponseDraft (spec §7).

Añade a ``BotResponseDraft`` los flags auditables del chequeo automático:
escalamiento, alucinación y negociación de precio, más el motivo de bloqueo.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("response_intelligence", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="botresponsedraft",
            name="auto_escalation",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="botresponsedraft",
            name="auto_hallucination",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="botresponsedraft",
            name="auto_discount",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="botresponsedraft",
            name="blocked_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
