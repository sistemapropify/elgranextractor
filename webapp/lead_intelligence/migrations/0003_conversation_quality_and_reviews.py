import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("lead_intelligence", "0002_leadconversationassessment"),
    ]

    operations = [
        migrations.AddField(
            model_name="leadconversationassessment",
            name="answered_request_items",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="leadconversationassessment",
            name="attention_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="leadconversationassessment",
            name="coverage_score",
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=5, null=True
            ),
        ),
        migrations.AddField(
            model_name="leadconversationassessment",
            name="directness_score",
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=5, null=True
            ),
        ),
        migrations.AddField(
            model_name="leadconversationassessment",
            name="first_response_confidence",
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=5, null=True
            ),
        ),
        migrations.AddField(
            model_name="leadconversationassessment",
            name="first_response_evidence",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="leadconversationassessment",
            name="first_response_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("adequate", "Adecuada"),
                    ("partial", "Parcial"),
                    ("inadequate", "Inadecuada"),
                    ("not_applicable", "No aplica"),
                    ("ambiguous", "Ambigua"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="leadconversationassessment",
            name="lead_request_items",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="leadconversationassessment",
            name="personalization_score",
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=5, null=True
            ),
        ),
        migrations.AddField(
            model_name="leadconversationassessment",
            name="relevance_score",
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=5, null=True
            ),
        ),
        migrations.AddField(
            model_name="leadconversationassessment",
            name="unanswered_request_items",
            field=models.JSONField(default=list),
        ),
        migrations.CreateModel(
            name="LeadConversationReview",
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
                ("history_hash", models.CharField(db_index=True, max_length=64)),
                (
                    "analysis_version",
                    models.CharField(db_index=True, max_length=40),
                ),
                (
                    "stage",
                    models.CharField(
                        choices=[
                            ("qualified", "Calificación"),
                            ("visit_intent", "Intención de visita"),
                            ("first_response", "Primera respuesta"),
                        ],
                        max_length=20,
                    ),
                ),
                ("ai_value", models.CharField(max_length=30)),
                ("human_value", models.CharField(max_length=30)),
                (
                    "verdict",
                    models.CharField(
                        choices=[
                            ("correct", "Correcto"),
                            ("incorrect", "Incorrecto"),
                            ("unsure", "Requiere discusión"),
                        ],
                        max_length=15,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(auto_now=True, db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lead_conversation_reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "prometeo_lead_conversation_review",
                "ordering": ["-reviewed_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="leadconversationreview",
            constraint=models.UniqueConstraint(
                fields=(
                    "source_lead_id",
                    "history_hash",
                    "analysis_version",
                    "stage",
                ),
                name="pli_unique_conversation_review",
            ),
        ),
        migrations.AddIndex(
            model_name="leadconversationreview",
            index=models.Index(
                fields=["analysis_version", "stage", "verdict"],
                name="pli_review_ver_stage_result",
            ),
        ),
    ]
