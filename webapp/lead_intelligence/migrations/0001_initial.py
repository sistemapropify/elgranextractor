from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AnalysisRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_type", models.CharField(choices=[("incremental", "Incremental"), ("daily", "Diario"), ("manual", "Manual")], max_length=20)),
                ("status", models.CharField(choices=[("running", "En ejecución"), ("completed", "Completado"), ("failed", "Fallido")], max_length=20)),
                ("started_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("leads_analyzed", models.PositiveIntegerField(default=0)),
                ("diagnoses_created", models.PositiveIntegerField(default=0)),
                ("actions_created", models.PositiveIntegerField(default=0)),
                ("rules_version", models.CharField(default="v1", max_length=40)),
                ("model_version", models.CharField(blank=True, max_length=80)),
                ("error_summary", models.TextField(blank=True)),
            ],
            options={"db_table": "prometeo_analysis_run", "ordering": ["-started_at"]},
        ),
        migrations.CreateModel(
            name="LeadDiagnosis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_lead_id", models.BigIntegerField(db_index=True)),
                ("diagnosis_code", models.CharField(db_index=True, max_length=60)),
                ("severity", models.CharField(choices=[("critical", "Crítica"), ("high", "Alta"), ("medium", "Media"), ("low", "Baja")], db_index=True, max_length=10)),
                ("reason", models.CharField(max_length=500)),
                ("evidence", models.JSONField(default=dict)),
                ("confidence", models.DecimalField(decimal_places=4, default=1, max_digits=5)),
                ("detected_at", models.DateTimeField()),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="diagnoses", to="lead_intelligence.analysisrun")),
            ],
            options={"db_table": "prometeo_lead_diagnosis"},
        ),
        migrations.CreateModel(
            name="RecommendedAction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_lead_id", models.BigIntegerField(db_index=True)),
                ("source_assigned_user_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("action_type", models.CharField(max_length=60)),
                ("priority", models.CharField(choices=[("critical", "Crítica"), ("high", "Alta"), ("medium", "Media"), ("low", "Baja")], db_index=True, max_length=10)),
                ("title", models.CharField(max_length=180)),
                ("reason", models.CharField(max_length=500)),
                ("suggested_channel", models.CharField(blank=True, max_length=20)),
                ("suggested_template_code", models.CharField(blank=True, max_length=100)),
                ("due_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("status", models.CharField(choices=[("pending", "Pendiente"), ("completed", "Completada"), ("dismissed", "Descartada"), ("expired", "Vencida")], db_index=True, default="pending", max_length=15)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("completed_by_source_user_id", models.BigIntegerField(blank=True, null=True)),
                ("diagnosis", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="actions", to="lead_intelligence.leaddiagnosis")),
            ],
            options={"db_table": "prometeo_recommended_action"},
        ),
        migrations.CreateModel(
            name="ActionOutcome",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("outcome_code", models.CharField(max_length=60)),
                ("notes", models.TextField(blank=True)),
                ("next_contact_at", models.DateTimeField(blank=True, null=True)),
                ("source_user_id", models.BigIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("action", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outcomes", to="lead_intelligence.recommendedaction")),
            ],
            options={"db_table": "prometeo_action_outcome", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="LeadMilestone",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_lead_id", models.BigIntegerField(db_index=True)),
                ("milestone_code", models.CharField(db_index=True, max_length=50)),
                ("first_reached_at", models.DateTimeField(db_index=True)),
                ("source_type", models.CharField(max_length=30)),
                ("source_reference_id", models.CharField(blank=True, max_length=100)),
                ("rules_version", models.CharField(default="v1", max_length=40)),
                ("confidence", models.DecimalField(decimal_places=4, default=1, max_digits=5)),
            ],
            options={"db_table": "prometeo_lead_milestone"},
        ),
        migrations.AddIndex(model_name="leaddiagnosis", index=models.Index(fields=["source_lead_id", "is_active"], name="pli_diag_lead_active")),
        migrations.AddIndex(model_name="leaddiagnosis", index=models.Index(fields=["severity", "detected_at"], name="pli_diag_sev_date")),
        migrations.AddIndex(model_name="recommendedaction", index=models.Index(fields=["source_assigned_user_id", "status", "due_at"], name="pli_action_agent_due")),
        migrations.AddConstraint(model_name="leadmilestone", constraint=models.UniqueConstraint(fields=("source_lead_id", "milestone_code", "rules_version"), name="pli_unique_milestone_version")),
    ]
