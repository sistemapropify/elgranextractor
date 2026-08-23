# -*- coding: utf-8 -*-
"""Fase 1 SPEC Eval Harness: modelo SkillVersion + FK en SkillExecution.

Creada manualmente porque makemigrations local está bloqueado por una
inconsistencia pre-existente en la BD 'propifai' (admin.0001_initial aplicada
antes de su dependencia intelligence.0001_initial).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("intelligence", "0024_aiconsumptionlog_trace_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="SkillVersion",
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
                ("skill_name", models.CharField(db_index=True, max_length=100)),
                ("version_hash", models.CharField(max_length=16)),
                ("description", models.TextField()),
                ("category", models.CharField(max_length=50)),
                ("access_level", models.IntegerField()),
                ("parameters_schema", models.JSONField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Versión de Skill",
                "verbose_name_plural": "Versiones de Skills",
                "db_table": "intelligence_skill_version",
            },
        ),
        migrations.AddField(
            model_name="skillexecution",
            name="skill_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="executions",
                to="intelligence.skillversion",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="skillversion",
            unique_together={("skill_name", "version_hash")},
        ),
        migrations.AddIndex(
            model_name="skillversion",
            index=models.Index(
                fields=["skill_name", "-created_at"],
                name="intel_skillver_name_date_idx",
            ),
        ),
    ]
