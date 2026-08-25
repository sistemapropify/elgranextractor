from django.core.management.base import BaseCommand, CommandError

from colas.scraping_tasks import _run_scraping
from ingestas.models import ScrapingJob


class Command(BaseCommand):
    help = "Reanuda un ScrapingJob usando los checkpoints guardados."

    def add_arguments(self, parser):
        parser.add_argument("job_id", type=int)

    def handle(self, *args, **options):
        job_id = options["job_id"]
        if not ScrapingJob.objects.filter(id=job_id).exists():
            raise CommandError(f"ScrapingJob #{job_id} no existe")

        updated = ScrapingJob.objects.filter(
            id=job_id,
            estado__in=('error', 'stopped', 'paused'),
        ).update(estado='idle', completado_en=None, mensaje_error=None)
        if not updated:
            raise CommandError(
                f"ScrapingJob #{job_id} no está en un estado reanudable"
            )

        self.stdout.write(f"Reanudando ScrapingJob #{job_id} desde sus checkpoints")
        _run_scraping(job_id)
        self.stdout.write(self.style.SUCCESS(f"ScrapingJob #{job_id} finalizado"))
