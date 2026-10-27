"""Resumable Azure background runner for the R2-to-D1 Geollaqta migration."""
import json
import threading
import time
import uuid

from . import geollaqta_bulk
from .master_d1 import Gateway
from .master_store import Conflict
from .storage import R2, StorageError

LEASE_PREFIX = 'migration:geollaqta:'
LEASE_SECONDS = 300
SAFE_BATCH_SIZE = 5
_threads = {}
_threads_lock = threading.RLock()


def _key(ubigeo):
    return LEASE_PREFIX + ubigeo


def _decode(value):
    try:
        data = json.loads(value or '{}')
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def job(gateway, ubigeo):
    rows = gateway.read('SELECT value FROM meta WHERE key=?', [_key(ubigeo)])
    value = _decode(rows[0]['value']) if rows else {}
    now = int(time.time())
    if value.get('status') == 'running' and int(value.get('expires_at', 0)) <= now:
        value['status'] = 'stale'
    return value


def _read_job(gateway, ubigeo):
    rows = gateway.read('SELECT value FROM meta WHERE key=?', [_key(ubigeo)])
    return _decode(rows[0]['value']) if rows else {}


def _write_job(gateway, ubigeo, value):
    key = _key(ubigeo)
    for attempt in range(6):
        revision = gateway.revision()
        next_revision = revision + 1
        value = {**value, 'updated_at': int(time.time()),
                 'expires_at': int(time.time()) + LEASE_SECONDS}
        result = {'revision': next_revision, 'job': value}
        changes = [
            {'table': 'meta',
             'upserts': [['revision', str(next_revision)], [key, json.dumps(value, ensure_ascii=False)]],
             'deletes': []},
        ]
        try:
            gateway.call({'action': 'commit', 'id': str(uuid.uuid4()),
                          'revision': revision, 'changes': changes, 'result': result})
            return value
        except Conflict:
            if attempt == 5:
                raise
    raise StorageError('No se pudo actualizar el estado de la migración.')


def _claim(gateway, ubigeo, actor, batch_size):
    for attempt in range(6):
        revision = gateway.revision()
        current = _read_job(gateway, ubigeo)
        now = int(time.time())
        if current.get('status') == 'running' and int(current.get('expires_at', 0)) > now:
            return False, current
        value = {
            'id': str(uuid.uuid4()),
            'ubigeo': ubigeo,
            'status': 'running',
            'actor': actor,
            'batch_size': batch_size,
            'attempts': (int(current.get('attempts', 0)) +
                         (1 if current.get('status') == 'error' else 0)),
            'started_at': now,
            'processed_lots': 0,
            'linked_lots': int(current.get('linked_lots', 0)),
            'pending_lots': int(current.get('pending_lots', 0)),
            'message': 'Migración iniciada en segundo plano.',
            'updated_at': now,
            'expires_at': now + LEASE_SECONDS,
        }
        next_revision = revision + 1
        changes = [{'table': 'meta', 'upserts': [
            ['revision', str(next_revision)],
            [_key(ubigeo), json.dumps(value, ensure_ascii=False)],
        ], 'deletes': []}]
        try:
            gateway.call({'action': 'commit', 'id': str(uuid.uuid4()),
                          'revision': revision, 'changes': changes,
                          'result': {'revision': next_revision, 'job': value}})
            return True, value
        except Conflict:
            if attempt == 5:
                raise
    raise StorageError('No se pudo reservar la migración en segundo plano.')


def start(ubigeo='040126', actor='sistema-geollaqta', batch_size=20):
    gateway = Gateway()
    batch_size = max(1, min(int(batch_size), SAFE_BATCH_SIZE))
    claimed, value = _claim(gateway, ubigeo, actor, batch_size)
    if not claimed:
        return {'started': False, 'job': value}
    with _threads_lock:
        running = _threads.get(ubigeo)
        if running and running.is_alive():
            return {'started': False, 'job': value}
        worker = threading.Thread(target=_run, args=(ubigeo, actor, batch_size, value['id']),
                                  name='geollaqta-migration-' + ubigeo, daemon=True)
        _threads[ubigeo] = worker
        worker.start()
    return {'started': True, 'job': value}


def _owns(gateway, ubigeo, job_id):
    current = _read_job(gateway, ubigeo)
    return current.get('id') == job_id and current.get('status') == 'running'


def _run(ubigeo, actor, batch_size, job_id):
    gateway = Gateway()
    cloud = R2(timeout=20)
    total = 0
    try:
        ids, truncated = geollaqta_bulk.lot_ids(ubigeo, cloud)
        linked = geollaqta_bulk.linked_lot_ids(gateway, ubigeo)
        pending = sorted(set(ids) - linked)
        linked_count = len(linked.intersection(ids))
        while pending and _owns(gateway, ubigeo, job_id):
            selected = pending[:batch_size]
            result = geollaqta_bulk.migrate_selected(
                gateway, ubigeo, selected, actor, cloud)
            total += len(selected)
            linked_count += len(selected)
            pending = pending[len(selected):]
            current = _read_job(gateway, ubigeo)
            value = {
                **current,
                'processed_lots': total,
                'linked_lots': linked_count,
                'pending_lots': len(pending),
                'last_batch_revision': result.get('revision'),
                'message': ('Vinculación terminada.' if not pending
                            else 'Migrando en tandas de ' + str(batch_size) + ' lotes.'),
                'status': 'done' if not pending else 'running',
            }
            _write_job(gateway, ubigeo, value)
        if pending and _owns(gateway, ubigeo, job_id):
            raise ValueError('La migración no pudo avanzar; revisa el siguiente manifiesto.')
    except Exception as error:
        current = _read_job(gateway, ubigeo)
        try:
            _write_job(gateway, ubigeo, {
                **current, 'status': 'error', 'processed_lots': total,
                'message': str(error), 'retryable': isinstance(error, (StorageError, OSError)),
            })
        except Exception:
            pass
    finally:
        with _threads_lock:
            _threads.pop(ubigeo, None)
