"""Windows-only native executor for explicitly assigned dashboard jobs."""
import ctypes
import os
import signal
import threading
from contextlib import contextmanager
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, transaction
from django.utils import timezone

from ingestas.models import ScrapingJob, ScrapingLog, ScrapingWorker
from ingestas.scraping_execution import can_execute, native_worker_identity


@contextmanager
def single_instance():
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.CreateMutexW(None, False, 'Local\\PropifyAdondevivirNativeWorker')
    if not handle:
        raise CommandError('No se pudo reservar el ejecutor local.')
    try:
        if ctypes.get_last_error() == 183:
            raise CommandError('El ejecutor local ya está abierto. No se inició otro.')
        yield
    finally:
        kernel.CloseHandle(handle)


def create_pilot(identity, url):
    from ingestas.views import _acquire_scraping_start_lock
    from scrapi.source_config import source_snapshot
    source = source_snapshot('adondevivir', url)
    with transaction.atomic():
        if not _acquire_scraping_start_lock() or ScrapingJob.objects.filter(
                estado__in=['idle', 'running', 'paused']).exists():
            raise CommandError('Hay otro trabajo activo. No se inició ni detuvo ningún scraping.')
        return ScrapingJob.objects.create(estado='idle', parametros={
            'portales': ['adondevivir'], 'execution_scope': 'local_interactive',
            'execution_host': identity, 'native_verification': True,
            'sources': {'adondevivir': source}, 'urls': {'adondevivir': source['source_url']},
            'limits': {'max_paginas': 1}, 'solo_listado': True, 'local_pilot': True,
        })


class Command(BaseCommand):
    help = 'Conecta la ventana real de esta PC con trabajos, logs y resultados de producción.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--job-id', type=int)
        parser.add_argument('--pilot-url', help='Prueba autorizada de una página, con guardado, sin triaje IA.')

    def handle(self, *args, **options):
        if os.name != 'nt':
            raise CommandError('El ejecutor nativo requiere Windows con escritorio abierto.')
        if options['pilot_url'] and options['job_id']:
            raise CommandError('Usa --pilot-url o --job-id, no ambos.')
        with single_instance():
            previous = os.environ.get('SCRAPING_LOCAL_NATIVE_WORKER')
            os.environ['SCRAPING_LOCAL_NATIVE_WORKER'] = '1'
            try:
                self._serve(options)
            finally:
                if previous is None:
                    os.environ.pop('SCRAPING_LOCAL_NATIVE_WORKER', None)
                else:
                    os.environ['SCRAPING_LOCAL_NATIVE_WORKER'] = previous

    def _serve(self, options):
        from colas.scraping_tasks import _run_scraping
        identity = native_worker_identity()
        revision = os.environ.get('SCRAPING_REVISION', 'local-native')[:64]
        stopping = threading.Event()
        health_stop = threading.Event()
        previous_signals = {}
        for kind in (signal.SIGINT, signal.SIGTERM):
            previous_signals[kind] = signal.signal(kind, lambda *_: stopping.set())

        def heartbeat():
            close_old_connections()
            ScrapingWorker.objects.update_or_create(identity=identity, defaults={
                'heartbeat_at': timezone.now(), 'revision': revision})

        def health():
            while not health_stop.wait(20):
                try:
                    heartbeat()
                except Exception as exc:
                    self.stderr.write('local.health_failed: ' + type(exc).__name__)
            close_old_connections()

        thread = None
        try:
            heartbeat()  # Fail before announcing readiness if SQL is inaccessible.
            thread = threading.Thread(target=health, daemon=True, name='local-native-health')
            thread.start()
            self.stdout.write('PC conectada: ' + identity + '. Inicia Adondevivir desde el dashboard.')
            if options['pilot_url']:
                options['job_id'] = create_pilot(identity, options['pilot_url']).pk
                options['once'] = True
            while not stopping.is_set():
                close_old_connections()
                self._recover_native(identity)
                query = ScrapingJob.objects.filter(estado='idle').order_by('creado_en')
                if options['job_id']:
                    query = query.filter(pk=options['job_id'])
                job = next((item for item in query[:200]
                            if can_execute(item.parametros, native_only=True)), None)
                if job:
                    self.stdout.write(f'Abriendo ventana para trabajo #{job.pk}.')
                    _run_scraping(job.pk, stop_event=stopping)
                    current = ScrapingJob.objects.get(pk=job.pk)
                    self.stdout.write(f'Trabajo #{job.pk}: {current.estado}; '
                                      f'{current.procesadas} procesadas, {current.errores} errores.')
                    if options['once']:
                        return
                elif options['job_id']:
                    raise CommandError('El trabajo no está disponible para esta PC; no se reclamó.')
                elif options['once']:
                    return
                else:
                    stopping.wait(5)
        finally:
            health_stop.set()
            if thread:
                thread.join(timeout=20)
            try:
                ScrapingWorker.objects.filter(identity=identity).update(
                    heartbeat_at=timezone.now() - timedelta(minutes=5))
            finally:
                close_old_connections()
                for kind, handler in previous_signals.items():
                    signal.signal(kind, handler)

    def _recover_native(self, identity):
        now = timezone.now()
        query = ScrapingJob.objects.filter(estado='running', lease_expires_at__lte=now)
        for job in query:
            if not can_execute(job.parametros, native_only=True):
                continue
            params = dict(job.parametros or {})
            count = int(params.get('auto_resume_count') or 0)
            updates = {'execution_token': None, 'lease_expires_at': None}
            if count >= 8:
                updates.update(estado='error', completado_en=now,
                               mensaje_error='Se agotaron las reanudaciones del proceso local.')
            else:
                params['auto_resume_count'] = count + 1
                updates.update(estado='idle', parametros=params)
            updated = ScrapingJob.objects.filter(pk=job.pk, estado='running',
                execution_token=job.execution_token, lease_expires_at__lte=now).update(**updates)
            if updated:
                ScrapingLog.log(job, 'warning', 'Proceso local interrumpido; checkpoint conservado.',
                                job.portal_actual, evento='worker.local_recovery')
