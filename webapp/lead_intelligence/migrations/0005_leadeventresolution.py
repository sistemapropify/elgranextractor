from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("lead_intelligence", "0004_current_analysis_version"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeadEventResolution",
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
                ("source_event_id", models.BigIntegerField(db_index=True)),
                (
                    "source_lead_id",
                    models.BigIntegerField(blank=True, db_index=True, null=True),
                ),
                (
                    "source_contact_id",
                    models.BigIntegerField(blank=True, db_index=True, null=True),
                ),
                (
                    "source_property_id",
                    models.BigIntegerField(blank=True, db_index=True, null=True),
                ),
                ("event_created_at", models.DateTimeField(blank=True, null=True)),
                ("event_scheduled_at", models.DateTimeField(blank=True, null=True)),
                ("resolution_method", models.CharField(db_index=True, max_length=40)),
                (
                    "resolution_status",
                    models.CharField(
                        choices=[
                            ("confirmed", "Confirmado"),
                            ("manual_review", "Revisión manual"),
                            ("unresolved", "Sin resolver"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                (
                    "confidence",
                    models.DecimalField(decimal_places=4, default=0, max_digits=5),
                ),
                ("candidate_count", models.PositiveIntegerField(default=0)),
                ("evidence", models.JSONField(default=dict)),
                ("resolver_version", models.CharField(db_index=True, max_length=40)),
                ("resolved_at", models.DateTimeField(db_index=True)),
            ],
            options={
                "db_table": "prometeo_lead_event_resolution",
                "ordering": ["-resolved_at"],
                "indexes": [
                    models.Index(
                        fields=["source_lead_id", "resolution_status"],
                        name="pli_event_lead_status",
                    ),
                    models.Index(
                        fields=["resolver_version", "resolution_status"],
                        name="pli_event_ver_status",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("source_event_id", "resolver_version"),
                        name="pli_unique_event_resolution_version",
                    )
                ],
            },
        ),
    ]
