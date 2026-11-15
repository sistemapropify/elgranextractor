from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("lead_intelligence", "0012_alter_analysisrunstep_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="leadconversationassessment",
            name="semantic_hash",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="durablejob",
            name="available_at",
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
            ),
        ),
    ]
