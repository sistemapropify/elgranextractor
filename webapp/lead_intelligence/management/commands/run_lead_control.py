"""Continuous local control without requiring a separate Redis installation."""
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction, close_old_connections
from django.utils import timezone

from lead_intelligence.control_engine import policy, observe
from lead_intelligence.control_source import source_snapshot, source_versions
from lead_intelligence.control_notifications import tick, send_pending
from lead_intelligence.control_digest import daily_digest
from lead_intelligence.control_runtime import write_status
from lead_intelligence.conversation_analysis import normalize_text
from lead_intelligence.models import LeadControlPolicy, LeadControlState

logger = logging.getLogger(__name__)


def refresh_lead(lead_id, version):
    close_old_connections()
    try:
        snapshot = source_snapshot(lead_id)
        snapshot['_control_source_version'] = version
        state = observe(snapshot)
        return state.quality
    finally:
        connections.close_all()


def run_clock(notify=False):
    close_old_connections()
    try:
        count = tick()
        if notify:
            send_pending(limit=100)
        daily_digest(send=notify)
        return count
    finally:
        connections.close_all()


def plan_refresh(rows, completed, busy, closed_statuses, changed_ids=()):
    """Changed known leads come before backlog; no ID/date cutoff."""
    closed = {normalize_text(s) for s in closed_statuses}
    unchanged, pending = [], []
    for lead_id, version, status in rows:
        if lead_id in busy:
            continue
        if completed.get(lead_id) == version:
            unchanged.append(lead_id)
        else:
            pending.append((lead_id, version, status))
    pending.sort(key=lambda row: (0 if row[0] in changed_ids or row[0] in completed else 1, normalize_text(row[2]) in closed, -row[0]))
    return unchanged, pending


class Command(BaseCommand):
    help = 'Revisa automáticamente toda la cartera y sus plazos. No envía mensajes ni notificaciones externas.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=int, default=60)
        parser.add_argument('--workers', type=int, default=4)
        parser.add_argument('--notify', action='store_true', help='Despachar los canales explícitamente habilitados en la configuración del servidor.')

    def handle(self, *args, **options):
        interval, workers = options['interval'], options['workers']
        if not 15 <= interval <= 300 or not 1 <= workers <= 8:
            raise CommandError('Intervalo: 15 a 300 segundos; trabajadores: 1 a 8.')
        settings = policy()
        if not settings.active_statuses or not settings.closed_statuses:
            raise CommandError('Guarda primero los estados activos y cerrados en Reglas.')
        token = uuid.uuid4().hex
        with transaction.atomic():
            locked = LeadControlPolicy.objects.select_for_update().get(pk=settings.pk)
            if locked.scan_lease_until and locked.scan_lease_until > timezone.now():
                raise CommandError('Ya hay otra revisión de control ejecutándose.')
            locked.scan_lease_token = token
            locked.scan_lease_until = timezone.now()+timedelta(minutes=5)
            locked.save(update_fields=['scan_lease_token', 'scan_lease_until'])
        completed = {row.source_lead_id: row.snapshot.get('_control_source_version') for row in LeadControlState.objects.only('source_lead_id', 'snapshot')}
        busy, pending, retry_after, previous_versions = {}, [], {}, {}
        updated = failures = total = 0
        next_poll = next_clock = next_lease = next_status = 0
        last_poll, error = None, ''
        clock_future = None
        pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='lead-control')
        clock_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='lead-deadlines')
        self.stdout.write('Control automático iniciado; transporte externo deshabilitado.')
        try:
            while True:
                now = time.monotonic()
                if now >= next_lease:
                    renewed = LeadControlPolicy.objects.filter(pk=settings.pk, scan_lease_token=token, scan_lease_until__gt=timezone.now()).update(scan_lease_until=timezone.now()+timedelta(minutes=5))
                    if not renewed:
                        raise CommandError('Se perdió la reserva del proceso de control.')
                    next_lease = now+30
                for lead_id, (future, version) in list(busy.items()):
                    if not future.done():
                        continue
                    del busy[lead_id]
                    try:
                        future.result()
                        completed[lead_id] = version
                        updated += 1
                    except Exception:
                        failures += 1
                        retry_after[lead_id] = now+60
                        # Never refresh the timestamp of a failed read.
                        LeadControlState.objects.filter(source_lead_id=lead_id).update(quality='unknown', last_error='No se pudo actualizar la conversación del CRM.')
                        logger.exception('No se pudo sincronizar lead %s', lead_id)
                if now >= next_poll:
                    try:
                        settings = policy()
                        rows = source_versions()
                        total = len(rows)
                        changed_ids = {lead_id for lead_id, version, _ in rows if previous_versions and previous_versions.get(lead_id) != version}
                        unchanged, pending = plan_refresh(rows, completed, busy, settings.closed_statuses, changed_ids)
                        previous_versions = {lead_id: version for lead_id, version, _ in rows}
                        read_at = timezone.now()
                        for offset in range(0, len(unchanged), 400):
                            LeadControlState.objects.filter(source_lead_id__in=unchanged[offset:offset+400]).update(observed_at=read_at)
                        last_poll, error = read_at.isoformat(), ''
                        self.stdout.write(f'Cartera: {total}; sin cambios: {len(unchanged)}; por incorporar/actualizar: {len(pending)}; procesados: {updated}; errores: {failures}')
                    except Exception:
                        error = 'No se pudo revisar la cartera del CRM; se reintentará automáticamente.'
                        logger.exception(error)
                    next_poll = time.monotonic()+interval
                # Independent workers allow new incoming messages to overtake the initial backlog.
                while pending and len(busy) < workers:
                    lead_id, version, _ = pending.pop(0)
                    if lead_id in busy or retry_after.get(lead_id, 0) > now:
                        continue
                    busy[lead_id] = (pool.submit(refresh_lead, lead_id, version), version)
                if clock_future and clock_future.done():
                    try:
                        clock_future.result()
                    except Exception:
                        logger.exception('No se pudieron revisar los plazos de control')
                    clock_future = None
                if now >= next_clock and clock_future is None:
                    clock_future = clock_pool.submit(run_clock, options['notify'])
                    next_clock = now+interval
                if now >= next_status:
                    write_status({'total': total, 'incorporated': len(completed), 'queued': len(pending), 'processing': len(busy), 'updated': updated, 'failures': failures, 'last_poll': last_poll, 'error': error, 'interval': interval})
                    next_status = now+5
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write('Deteniendo control automático.')
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
            clock_pool.shutdown(wait=True, cancel_futures=True)
            LeadControlPolicy.objects.filter(pk=settings.pk, scan_lease_token=token).update(scan_lease_until=None, scan_lease_token='')
            write_status({'error': 'Proceso detenido.', 'total': total, 'incorporated': len(completed)})
