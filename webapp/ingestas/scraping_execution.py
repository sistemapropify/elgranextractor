"""Explicit execution routing; a native PC job must never fall back to Azure."""
import os
import socket
from datetime import timedelta

from django.utils import timezone

LOCAL_PREFIX = 'adondevivir-pc:'


def native_worker_identity(host=None):
    return LOCAL_PREFIX + (host or socket.gethostname()).lower()[:110]


def can_execute(params, *, native_only=False):
    params = params or {}
    if params.get('native_verification'):
        return bool(os.name == 'nt'
                    and os.environ.get('SCRAPING_LOCAL_NATIVE_WORKER') == '1'
                    and params.get('execution_scope') == 'local_interactive'
                    and params.get('execution_host') == native_worker_identity()
                    and 'adondevivir' in (params.get('portales') or []))
    if native_only:
        return False
    return not (params.get('execution_scope') == 'local_interactive' and os.name != 'nt')


def local_worker_status(identity=None):
    from .models import ScrapingWorker
    workers = ScrapingWorker.objects.filter(identity__startswith=LOCAL_PREFIX)
    if identity:
        workers = workers.filter(identity=identity)
    latest = workers.order_by('-heartbeat_at').first()
    ready = bool(latest and latest.heartbeat_at >= timezone.now() - timedelta(seconds=75))
    return {'ready': ready, 'identity': latest.identity if ready else None,
            'message': 'PC conectada: ' + latest.identity[len(LOCAL_PREFIX):] if ready
            else 'PC desconectada: inicia start-adondevivir-worker.ps1 en tu computadora.'}
