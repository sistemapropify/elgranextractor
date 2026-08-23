"""SPEC Fase 3 — Calcula métricas diarias por skill desde intelligence_skill_execution.

Usa p50/p95 (numpy.percentile), NO AVG, porque el promedio esconde outliers.
Upsert en SkillDailyMetric (no duplica filas). Programar vía cron / Celery beat
a las 00:15 America/Lima para el día anterior.

Uso:
    python manage.py compute_daily_skill_metrics            # ayer
    python manage.py compute_daily_skill_metrics --date 2026-08-20   # fecha concreta
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

import numpy as np

from intelligence.models import SkillDailyMetric, SkillExecution


class Command(BaseCommand):
    help = "Calcula métricas diarias por skill desde intelligence_skill_execution"

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default="", help="YYYY-MM-DD (default: ayer)")

    def handle(self, *args, **options):
        if options["date"]:
            target_date = date.fromisoformat(options["date"])
        else:
            target_date = timezone.localdate() - timedelta(days=1)

        rows = SkillExecution.objects.filter(executed_at__date=target_date)
        by_skill = {}
        for row in rows:
            by_skill.setdefault(row.skill_name, []).append(row)

        updated = 0
        for skill_name, execs in by_skill.items():
            latencies = [
                e.latency_ms for e in execs
                if e.status == "success" and e.latency_ms
            ]
            success = sum(1 for e in execs if e.status == "success")
            _, created = SkillDailyMetric.objects.update_or_create(
                skill_name=skill_name,
                date=target_date,
                defaults=dict(
                    executions=len(execs),
                    success_count=success,
                    error_count=sum(1 for e in execs if e.status == "error"),
                    cached_count=sum(1 for e in execs if e.cached),
                    latency_p50_ms=float(np.percentile(latencies, 50)) if latencies else None,
                    latency_p95_ms=float(np.percentile(latencies, 95)) if latencies else None,
                    success_rate=success / len(execs) if execs else 0,
                ),
            )
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"SkillDailyMetric para {target_date}: {updated} skills · "
                f"{len(rows)} ejecuciones"
            )
        )
