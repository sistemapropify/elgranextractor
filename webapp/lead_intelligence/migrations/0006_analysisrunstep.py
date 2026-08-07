from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lead_intelligence", "0005_leadeventresolution"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnalysisRunStep",
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
                ("lead_id", models.PositiveIntegerField(blank=True, null=True)),
                ("status", models.CharField(default="processed", max_length=20)),
                ("message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="steps",
                        to="lead_intelligence.analysisrun",
                    ),
                ),
            ],
            options={
                "db_table": "prometeo_analysis_run_step",
                "ordering": ["created_at", "id"],
            },
        ),
    ]
