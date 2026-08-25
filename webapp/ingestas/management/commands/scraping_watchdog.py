"""Ejecutor persistente y autorrecuperable para scraping en producción."""

import os
import signal
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.db.models import Q
from django.utils import timezone

from colas.scraping_tasks import _run_scraping
from ingestas.models import ScrapingJob, ScrapingLog


class Command(BaseCommand):
    help = 'Ejecuta y recupera trabajos de scraping desde sus checkpoints.'

    def handle(self, *args, **options):
        poll_seconds = int(os.environ.get('SCRAPING_WATCHDOG_POLL_SECONDS', '20'))
        stale_seconds = int(os.environ.get('SCRAPING_WATCHDOG_STALE_SECONDS', '180'))
        max_resumes = int(os.environ.get('SCRAPING_MAX_AUTO_RESUMES', '8'))
        stopping = False

        def stop(*_args):
            nonlocal stopping
            stopping = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        self.stdout.write(self.style.SUCCESS('Scraping watchdog iniciado'))

        while not stopping:
            close_old_connections()
            try:
                self._recover_orphan(stale_seconds, max_resumes)
                job_id = ScrapingJob.objects.filter(estado='idle').order_by('creado_en').values_list('id', flat=True).first()
                if job_id:
                    self.stdout.write(f'Ejecutando ScrapingJob #{job_id}')
                    _run_scraping(job_id)
                    continue
            except Exception as exc:
                self.stderr.write(f'Watchdog: {type(exc).__name__}: {exc}')
                close_old_connections()
            time.sleep(max(5, poll_seconds))

        close_old_connections()

    def _recover_orphan(self, stale_seconds, max_resumes):
        cutoff = timezone.now() - timedelta(seconds=stale_seconds)
        orphaned = list(ScrapingJob.objects.filter(
            estado='running', completado_en__isnull=True
        ).filter(
            Q(iniciado_en__lt=cutoff) | Q(iniciado_en__isnull=True, creado_en__lt=cutoff)
        ).exclude(logs__timestamp__gte=cutoff).distinct())

        # Los timeouts internos terminan de forma ordenada en estado error;
        # también deben continuar sin intervención, pero solo para el job más
        # reciente y durante una ventana acotada para no revivir históricos.
        latest_error = ScrapingJob.objects.filter(
            estado='error',
            completado_en__gte=timezone.now() - timedelta(hours=1),
        ).order_by('-creado_en').first()
        candidates = orphaned
        if latest_error and self._is_recoverable_error(latest_error):
            candidates.append(latest_error)

        for job in candidates:
            parametros = dict(job.parametros or {})
            resumes = int(parametros.get('auto_resume_count', 0) or 0)
            if resumes >= max_resumes:
                ScrapingJob.objects.filter(id=job.id, estado='running').update(
                    estado='error', completado_en=timezone.now(),
                    mensaje_error=f'Se agotaron {max_resumes} reanudaciones automáticas.',
                )
                continue

            parametros['auto_resume_count'] = resumes + 1
            parametros['last_auto_resume_at'] = timezone.now().isoformat()
            claimed = ScrapingJob.objects.filter(id=job.id, estado=job.estado).update(
                estado='idle', parametros=parametros, iniciado_en=None,
                completado_en=None, mensaje_error=None,
            )
            if claimed:
                ScrapingLog.log(
                    job, 'warning',
                    f'♻️ Proceso interrumpido; reanudación automática {resumes + 1}/{max_resumes} desde el último checkpoint.',
                    job.portal_actual,
                )

    @staticmethod
    def _is_recoverable_error(job):
        parametros = dict(job.parametros or {})
        resultados = dict(parametros.get('resultados_por_portal') or {})
        text = ' '.join(
            [str(job.mensaje_error or '')]
            + [str((data or {}).get('mensaje') or '') for data in resultados.values()]
        ).lower()
        markers = (
            'timeout', 'superó el timeout', 'fallo en pagina',
            'checkpoint previo conservado', 'camoufox fallo',
            'ejecución huérfana', 'proceso interrumpido',
        )
        return any(marker in text for marker in markers)
