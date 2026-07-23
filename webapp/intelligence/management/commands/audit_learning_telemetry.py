import json
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone

from intelligence.models import SystemTrace


class Command(BaseCommand):
    help = "Audita cobertura y validez básica de la telemetría PIL."

    def add_arguments(self, parser):
        parser.add_argument('--since-hours', type=int, default=24)
        parser.add_argument('--fail-on-coverage-below', type=float, default=None)
        parser.add_argument('--json', action='store_true', dest='as_json')

    def handle(self, *args, **options):
        hours = max(1, options['since_hours'])
        since = timezone.now() - timedelta(hours=hours)
        traces = SystemTrace.objects.filter(started_at__gte=since)
        total = traces.count()
        started = traces.filter(status='started').count()
        finalized = total - started
        coverage = finalized / total if total else 0.0

        statuses = {
            row['status']: row['total']
            for row in traces.values('status').annotate(total=Count('id'))
        }
        missing_versions = traces.filter(code_version='unknown').count()
        without_events = traces.annotate(
            event_count=Count('events')
        ).filter(event_count=0).count()

        report = {
            'window_hours': hours,
            'total_traces': total,
            'finalized_traces': finalized,
            'coverage': round(coverage, 4),
            'status_distribution': statuses,
            'traces_without_events': without_events,
            'unknown_code_version': missing_versions,
            'mutation_enabled': False,
        }

        if options['as_json']:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(f"Ventana: {hours} horas")
            self.stdout.write(f"Trazas: {total}")
            self.stdout.write(f"Finalizadas: {finalized}")
            self.stdout.write(f"Cobertura: {coverage:.1%}")
            self.stdout.write(f"Sin eventos: {without_events}")
            self.stdout.write(f"Versión desconocida: {missing_versions}")
            self.stdout.write("Mutación automática: DESHABILITADA")

        threshold = options['fail_on_coverage_below']
        if threshold is not None and coverage < threshold:
            raise CommandError(
                f"Cobertura {coverage:.2%} debajo del mínimo {threshold:.2%}"
            )

