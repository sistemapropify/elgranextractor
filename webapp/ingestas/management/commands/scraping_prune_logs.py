from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from ingestas.models import ScrapingJob, ScrapingLog


class Command(BaseCommand):
    help = 'Retención de logs de trabajos terminados; simulación por defecto.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if options['days'] < 7:
            raise CommandError('La retención mínima es 7 días.')
        cutoff = timezone.now() - timedelta(days=options['days'])
        query = ScrapingLog.objects.filter(timestamp__lt=cutoff,
            job__estado__in=['completed', 'error', 'stopped'])
        count = query.count()
        if options['apply']:
            count = 0
            job_ids = list(query.order_by().values_list('job_id', flat=True).distinct())
            for job_id in job_ids:
                while True:
                    with transaction.atomic():
                        job = ScrapingJob.objects.select_for_update().get(pk=job_id)
                        if job.estado not in ('completed', 'error', 'stopped'):
                            break
                        ids = list(query.filter(job_id=job_id).values_list('pk', flat=True)[:1000])
                        if not ids:
                            break
                        deleted, _ = ScrapingLog.objects.filter(pk__in=ids).delete()
                        count += deleted
        self.stdout.write(f'{count} logs {"eliminados" if options["apply"] else "elegibles (simulación)"}')
