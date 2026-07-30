from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lead_intelligence", "0003_conversation_quality_and_reviews"),
    ]

    operations = [
        migrations.AddField(
            model_name="analysisrun",
            name="heartbeat_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="analysisrun",
            name="leads_failed",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="analysisrun",
            name="leads_skipped",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="analysisrun",
            name="leads_total",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="leadconversationassessment",
            name="analysis_version",
            field=models.CharField(default="context-v2", max_length=40),
        ),
    ]
