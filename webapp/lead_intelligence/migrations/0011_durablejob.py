from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("lead_intelligence", "0010_lead_control")]
    operations = [
        migrations.CreateModel(
            name="DurableJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("lead_analysis", "Análisis de leads"), ("shadow_reconcile", "Reconciliación shadow"), ("scraping", "Scraping")], db_index=True, max_length=32)),
                ("status", models.CharField(choices=[("pending", "Pendiente"), ("running", "En ejecución"), ("completed", "Completado"), ("failed", "Fallido"), ("cancelled", "Cancelado")], db_index=True, default="pending", max_length=16)),
                ("dedupe_key", models.CharField(max_length=160, unique=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=3)),
                ("lease_until", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("heartbeat_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("error_summary", models.TextField(blank=True, default="")),
            ],
            options={"db_table": "prometeo_durable_job", "ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(model_name="durablejob", index=models.Index(fields=["status", "lease_until"], name="durable_status_lease")),
    ]
