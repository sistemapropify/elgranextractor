import json
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from django.utils import timezone
from ingestas.models import EjecucionPortal, ScrapingCandidate, ScrapingJob
from ingestas.scraping_health import worker_health


class Command(BaseCommand):
    help = 'Métricas JSON y señales de incidencia para el monitor existente; no envía mensajes.'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, choices=range(1, 169), default=24, metavar='1..168')

    def handle(self, *args, **options):
        now = timezone.now()
        since = now - timedelta(hours=options['hours'])
        jobs = ScrapingJob.objects.filter(creado_en__gte=since)
        runs = EjecucionPortal.objects.filter(iniciado_en__gte=since)
        health = worker_health()
        expired = ScrapingJob.objects.filter(estado='running', lease_expires_at__lte=now).count()
        failed = jobs.filter(estado='error').count()
        oldest = ScrapingJob.objects.filter(estado='idle').order_by('creado_en').first()
        queue_age = int((now - oldest.creado_en).total_seconds()) if oldest else 0
        issues = []
        for condition, code in ((not health['ready'], 'worker.unavailable'),
                                (expired, 'execution.lease_expired'),
                                (failed, 'job.failed'), (queue_age > 600, 'queue.delayed')):
            if condition:
                issues.append(code)
        report = {'at': now.isoformat(), 'hours': options['hours'], 'worker': health,
            'queue_oldest_seconds': queue_age, 'expired_leases': expired, 'issues': issues,
            'jobs': list(jobs.values('estado').annotate(count=Count('id')).order_by('estado')),
            'portals': list(runs.values('portal', 'estado').annotate(count=Count('id'),
                seen=Sum('propiedades_vistas'), retired=Sum('retiros_confirmados')).order_by('portal', 'estado')),
            'candidates': list(ScrapingCandidate.objects.filter(run__in=runs).values('status')
                .annotate(count=Count('id')).order_by('status'))}
        self.stdout.write(json.dumps(report))
