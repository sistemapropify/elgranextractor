import json
import logging
import signal
import threading
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connection
from ingestas.ml_candidates import process_pending, reconcile_chunk, schema_ready

from ingestas.ml_context import process_spatial, process_identity

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Evalúa candidatas ML y completa antigüedad con evidencia; no entrena modelos.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Un lote de evaluación y conciliación.')
        parser.add_argument('--reconcile', action='store_true', help='Completar un barrido reanudable del histórico y salir con --once.')
        parser.add_argument('--retry-errors', action='store_true')
        parser.add_argument('--batch-size', type=int, default=50)

    def handle(self, *args, **options):
        from ingestas.models import MLObservation, MLCandidate
        if connection.vendor == 'microsoft':
            db_options = connection.settings_dict.setdefault('OPTIONS', {})
            db_options.setdefault('query_timeout', 60)
            db_options.setdefault('connection_timeout', 15)
            db_options.setdefault('connection_retries', 1)
        stop = threading.Event()
        if not options['once']:
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda *_: stop.set())
        batch = max(1, min(options['batch_size'], 200))
        retried = False
        totals = dict(scanned=0, queued=0, processed=0, repaired=0, errors=0)
        while not stop.is_set():
            close_old_connections()
            try:
                if not schema_ready():
                    self.stderr.write('ml.schema.pending: aplicar migración ingestas antes de evaluar.')
                    if options['once']:
                        raise CommandError('Esquema ML pendiente')
                    stop.wait(30)
                    continue
                if options['retry_errors'] and not retried:
                    MLObservation.objects.filter(status='error').update(status='pending', attempts=0)
                    MLCandidate.objects.filter(status='error').update(status='pending')
                    retried = True
                progress = reconcile_chunk(batch, force=options['reconcile'])
                result = process_pending(batch)
                context = process_spatial(batch)
                identity = process_identity() if not MLObservation.objects.filter(status='pending').exists() else {}
                for key in totals:
                    totals[key] += progress.get(key, 0) + result.get(key, 0)
                self.stdout.write(json.dumps({'event': 'ml.pipeline.progress', **progress, **result, **context, **identity}))
                if options['once'] and (not options['reconcile'] or progress['complete']):
                    while options['reconcile'] and MLObservation.objects.filter(status='pending').exists():
                        drained = process_pending(batch)
                        for key in drained:
                            totals[key] += drained[key]
                    if options['reconcile']:
                        while process_spatial(batch)['spatial_pending']:
                            pass
                        self.stdout.write(json.dumps({'event': 'ml.identity.finished', **process_identity(force=True)}))
                    remaining_errors = MLCandidate.objects.filter(status='error').count()
                    self.stdout.write(json.dumps({'event': 'ml.pipeline.finished', **totals,
                        'pending_versions': MLObservation.objects.filter(status='pending').count(),
                        'candidate_errors': remaining_errors}))
                    if options['reconcile'] and remaining_errors:
                        raise CommandError('Hay candidatas con error; revisar el log y reintentar.')
                    return
            except Exception:
                if options['once']:
                    raise
                logger.exception('ml.worker.failed; se conserva el cursor')
                stop.wait(20)
            if not options['once']:
                stop.wait(5)
