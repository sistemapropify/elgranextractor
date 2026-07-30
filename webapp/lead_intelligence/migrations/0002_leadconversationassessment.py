from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lead_intelligence", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="LeadConversationAssessment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_lead_id", models.BigIntegerField(db_index=True)),
                ("history_hash", models.CharField(db_index=True, max_length=64)),
                ("analysis_version", models.CharField(default="context-v1", max_length=40)),
                ("qualified_status", models.CharField(choices=[("confirmed", "Confirmado"), ("not_confirmed", "No confirmado"), ("ambiguous", "Ambiguo")], max_length=20)),
                ("visit_intent_status", models.CharField(choices=[("confirmed", "Confirmado"), ("not_confirmed", "No confirmado"), ("ambiguous", "Ambiguo")], max_length=20)),
                ("qualified_confidence", models.DecimalField(decimal_places=4, max_digits=5)),
                ("visit_intent_confidence", models.DecimalField(decimal_places=4, max_digits=5)),
                ("qualified_evidence", models.JSONField(default=list)),
                ("visit_intent_evidence", models.JSONField(default=list)),
                ("reason", models.TextField(blank=True)),
                ("model_version", models.CharField(max_length=80)),
                ("analyzed_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "db_table": "prometeo_lead_conversation_assessment",
                "ordering": ["-analyzed_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="leadconversationassessment",
            constraint=models.UniqueConstraint(
                fields=("source_lead_id", "history_hash", "analysis_version"),
                name="pli_unique_conversation_assessment",
            ),
        ),
        migrations.AddIndex(
            model_name="leadconversationassessment",
            index=models.Index(
                fields=["source_lead_id", "analysis_version", "analyzed_at"],
                name="pli_assess_lead_ver_date",
            ),
        ),
    ]
