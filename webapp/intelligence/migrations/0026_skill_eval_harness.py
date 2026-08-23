# -*- coding: utf-8 -*-
"""Fases 2 y 3 SPEC Eval Harness: eval set de enrutamiento + scorecard diario.

Creada manualmente (makemigrations local bloqueado por inconsistencia
pre-existente en la BD 'propifai').
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("intelligence", "0025_skillversion"),
    ]

    operations = [
        migrations.CreateModel(
            name="SkillEvalCase",
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
                ("query", models.TextField()),
                ("expected_skill", models.CharField(db_index=True, max_length=100)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Caso de Eval de Enrutamiento",
                "verbose_name_plural": "Casos de Eval de Enrutamiento",
                "db_table": "intelligence_skill_eval_case",
            },
        ),
        migrations.CreateModel(
            name="SkillEvalRun",
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
                ("run_at", models.DateTimeField(auto_now_add=True)),
                ("total_cases", models.IntegerField()),
                ("correct", models.IntegerField()),
                ("accuracy", models.FloatField()),
                ("threshold_used", models.FloatField()),
                ("notes", models.CharField(blank=True, max_length=255)),
            ],
            options={
                "verbose_name": "Run de Eval de Enrutamiento",
                "verbose_name_plural": "Runs de Eval de Enrutamiento",
                "db_table": "intelligence_skill_eval_run",
                "ordering": ["-run_at"],
            },
        ),
        migrations.CreateModel(
            name="SkillEvalResult",
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
                ("predicted_skill", models.CharField(max_length=100)),
                ("is_correct", models.BooleanField()),
                ("similarity_score", models.FloatField(null=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="intelligence.skillevalrun",
                    ),
                ),
                (
                    "case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="intelligence.skillevalcase",
                    ),
                ),
            ],
            options={
                "verbose_name": "Resultado de Eval",
                "verbose_name_plural": "Resultados de Eval",
                "db_table": "intelligence_skill_eval_result",
            },
        ),
        migrations.CreateModel(
            name="SkillDailyMetric",
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
                ("date", models.DateField(db_index=True)),
                ("executions", models.IntegerField(default=0)),
                ("success_count", models.IntegerField(default=0)),
                ("error_count", models.IntegerField(default=0)),
                ("cached_count", models.IntegerField(default=0)),
                ("latency_p50_ms", models.FloatField(null=True)),
                ("latency_p95_ms", models.FloatField(null=True)),
                ("success_rate", models.FloatField(default=0.0)),
            ],
            options={
                "verbose_name": "Métrica Diaria de Skill",
                "verbose_name_plural": "Métricas Diarias de Skills",
                "db_table": "intelligence_skill_daily_metric",
            },
        ),
        migrations.AlterUniqueTogether(
            name="skilldailymetric",
            unique_together={("skill_name", "date")},
        ),
    ]
