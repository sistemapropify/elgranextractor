from django.conf import settings
from django.db import migrations, models

import response_intelligence.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("lead_intelligence", "0007_analysisrun_period"),
    ]

    operations = [
        migrations.CreateModel(
            name="CuratedExample",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("source_lead_id", models.BigIntegerField(db_index=True)),
                (
                    "source_assessment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="curated_examples",
                        to="lead_intelligence.leadconversationassessment",
                    ),
                ),
                (
                    "intent_category",
                    models.CharField(
                        choices=[
                            ("precio", "Precio"),
                            ("ubicacion", "Ubicación"),
                            ("visita", "Visita"),
                            ("financiamiento", "Financiamiento"),
                            ("objecion_precio", "Objeción de precio"),
                            ("disponibilidad", "Disponibilidad"),
                            ("otro", "Otro"),
                        ],
                        db_index=True,
                        max_length=24,
                    ),
                ),
                ("client_message", models.TextField(blank=True, default="")),
                ("agent_response", models.TextField(blank=True, default="")),
                ("quality_scores", models.JSONField(blank=True, default=dict)),
                ("approved", models.BooleanField(db_index=True, default=False)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="curated_example_approvals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "prometeo_curated_example",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="BusinessRule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("rule_text", models.TextField()),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("prohibicion", "Prohibición"),
                            ("tono", "Tono"),
                            ("escalamiento", "Escalamiento"),
                        ],
                        max_length=20,
                    ),
                ),
                ("active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "prometeo_business_rule",
                "ordering": ["category", "id"],
            },
        ),
        migrations.CreateModel(
            name="BotResponseDraft",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("source_lead_id", models.BigIntegerField(db_index=True)),
                ("client_message", models.TextField(blank=True, default="")),
                (
                    "intent_category",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("precio", "Precio"),
                            ("ubicacion", "Ubicación"),
                            ("visita", "Visita"),
                            ("financiamiento", "Financiamiento"),
                            ("objecion_precio", "Objeción de precio"),
                            ("disponibilidad", "Disponibilidad"),
                            ("otro", "Otro"),
                        ],
                        db_index=True,
                        default="",
                        max_length=24,
                    ),
                ),
                ("prompt_snapshot", models.JSONField(blank=True, default=dict)),
                ("generated_response", models.TextField(blank=True, default="")),
                ("property_data_used", models.JSONField(blank=True, default=list)),
                (
                    "mode",
                    models.CharField(
                        choices=[
                            ("sandbox", "Sandbox offline"),
                            ("shadow_live", "Shadow en vivo"),
                            ("production", "Producción"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("model_version", models.CharField(blank=True, default="", max_length=80)),
                (
                    "trace_id",
                    models.CharField(blank=True, db_index=True, default="", max_length=64),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "db_table": "prometeo_bot_response_draft",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="BotResponseEvaluation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "draft",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="evaluations",
                        to="response_intelligence.botresponsedraft",
                    ),
                ),
                (
                    "verdict",
                    models.CharField(
                        choices=[
                            ("correct", "Correcto"),
                            ("incorrect", "Incorrecto"),
                            ("acceptable_with_adjustment", "Aceptable con ajuste"),
                        ],
                        max_length=30,
                    ),
                ),
                ("hallucination_flag", models.BooleanField(default=False)),
                ("tone_flag", models.BooleanField(default=False)),
                ("would_send", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True, default="")),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="bot_response_evaluations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("reviewed_at", models.DateTimeField(auto_now=True, db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "prometeo_bot_response_evaluation",
                "ordering": ["-reviewed_at"],
            },
        ),
        migrations.AddIndex(
            model_name="curatedexample",
            index=models.Index(
                fields=["intent_category", "active", "approved"],
                name="curated_cat_active_approved",
            ),
        ),
        migrations.AddIndex(
            model_name="botresponsedraft",
            index=models.Index(
                fields=["mode", "created_at"], name="draft_mode_date"
            ),
        ),
        migrations.AddIndex(
            model_name="botresponsedraft",
            index=models.Index(
                fields=["source_lead_id", "created_at"], name="draft_lead_date"
            ),
        ),
        migrations.AddIndex(
            model_name="botresponseevaluation",
            index=models.Index(
                fields=["verdict", "reviewed_at"], name="eval_verdict_date"
            ),
        ),
    ]
