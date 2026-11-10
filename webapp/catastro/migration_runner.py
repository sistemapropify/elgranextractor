"""Resumable Azure background runner for the R2-to-D1 Geollaqta migration."""
import json
import threading
import time
import uuid

from . import geollaqta_bulk
from . import cofopri_vector_migration
from .formalization_detail_migration import migrate_formalization_details
from .master_d1 import Gateway
from .migration_audit import audit_district
from .master_store import Conflict
from .storage import R2, StorageError

LEASE_PREFIX = 'migration:geollaqta:'
LEASE_SECONDS = 300
SAFE_BATCH_SIZE = 200
ALL_SCOPE = 'all'
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


def start(ubigeo='040126', actor='sistema-geollaqta',
          batch_size=SAFE_BATCH_SIZE):
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


def start_all(actor='sistema-geollaqta', batch_size=SAFE_BATCH_SIZE):
    """Start one resumable migration across every district with R2 data."""
    gateway = Gateway()
    batch_size = max(1, min(int(batch_size), SAFE_BATCH_SIZE))
    claimed, value = _claim(gateway, ALL_SCOPE, actor, batch_size)
    if not claimed:
        return {'started': False, 'job': value}
    with _threads_lock:
        running = _threads.get(ALL_SCOPE)
        if running and running.is_alive():
            return {'started': False, 'job': value}
        worker = threading.Thread(
            target=_run_all,
            args=(actor, batch_size, value['id']),
            name='geollaqta-migration-all',
            daemon=True,
        )
        _threads[ALL_SCOPE] = worker
        worker.start()
    return {'started': True, 'job': value}


def _owns(gateway, ubigeo, job_id):
    current = _read_job(gateway, ubigeo)
    return current.get('id') == job_id and current.get('status') == 'running'


def _audit_job(gateway, ubigeo, expected_lots, current):
    audit = audit_district(
        gateway, ubigeo, expected_lots, revision=gateway.revision())
    passed = audit['status'] != 'failed'
    return _write_job(gateway, ubigeo, {
        **current,
        'linked_lots': audit['linked_lots'],
        'pending_lots': 0,
        'status': 'done' if passed else 'error',
        'message': (
            'Migración y auditoría completas: ' +
            str(audit['linked_lots']) + ' lotes verificados.'
            if passed else
            'Auditoría bloqueó la publicación: ' +
            ' '.join(audit['errors'])),
        'audit': audit,
        'retryable': False,
    })


def audit_existing(ubigeo='040126', actor='azure-migration-watchdog'):
    """Audit a completed migration that predates the integrity gate."""
    gateway = Gateway()
    cloud = R2(timeout=20)
    ids, truncated = geollaqta_bulk.lot_ids(ubigeo, cloud)
    if truncated:
        raise ValueError('El inventario R2 está truncado; no se puede aprobar la auditoría.')
    if not ids:
        raise ValueError('No hay lotes R2 para auditar.')
    current = _read_job(gateway, ubigeo)
    if current.get('status') != 'done':
        raise ValueError('La migración no está terminada.')
    if current.get('audit'):
        return current
    return _audit_job(gateway, ubigeo, ids, current)


def _run(ubigeo, actor, batch_size, job_id, progress=None):
    gateway = Gateway()
    cloud = R2(timeout=20)
    total = 0
    details_imported = False
    details_import = None
    try:
        from cuadrantizacion import geollaqta
        ids, truncated = geollaqta_bulk.lot_ids(ubigeo, cloud)
        if truncated:
            raise ValueError('El inventario R2 está truncado; divide el ámbito antes de migrar.')
        try:
            formal_lots = cofopri_vector_migration.merged_formalization_lots(
                ubigeo, cloud)
        except (ValueError, StorageError, AttributeError):
            formal_lots = []
        inventory = (ids, truncated)
        while _owns(gateway, ubigeo, job_id):
            advanced = False
            status = geollaqta_bulk.migration_status(
                gateway, ubigeo, cloud, inventory=inventory,
                formal_lots=formal_lots)
            if status['formalization_pending_lots']:
                formal = cofopri_vector_migration.migrate_direct(
                    gateway,
                    ubigeo, geollaqta.DISTRICTS[ubigeo]['name'],
                    batch_size=min(batch_size, 200),
                    limit=min(batch_size, 200), actor=actor)
                processed = int(formal['unique_formalization_lots'])
                advanced = processed > 0
                batch_revision = (
                    formal['batches'][-1]['revision']
                    if formal.get('batches') else None)
            elif status['pcdpi_pending_lots']:
                selected = min(batch_size, 50)
                result = geollaqta_bulk.migrate_pending(
                    gateway, ubigeo, selected, actor, cloud)
                processed = int(result.get('processed_lots', 0))
                advanced = processed > 0
                batch_revision = result.get('batch_revision')
            elif formal_lots and not details_imported:
                details_import = migrate_formalization_details(
                    gateway,
                    ubigeo,
                    geollaqta.DISTRICTS[ubigeo]['name'],
                    formal_lots,
                    batch_size=5,
                    actor=actor,
                    cloud=cloud,
                )
                details_imported = True
                processed = 0
                batch_revision = None
                advanced = True
            else:
                processed = 0
                batch_revision = None
            total += processed
            status = geollaqta_bulk.migration_status(
                gateway, ubigeo, cloud, inventory=inventory,
                formal_lots=formal_lots)
            current = _read_job(gateway, ubigeo)
            value = {
                **current,
                'processed_lots': total,
                'linked_lots': status['linked_lots'],
                'pending_lots': status['pending_lots'],
                'last_batch_revision': batch_revision,
                'formalization_details': details_import,
                'message': ('Vinculación terminada.' if not status['pending_lots']
                            else 'Migrando en tandas de ' + str(batch_size) + ' lotes.'),
                'status': 'done' if not status['pending_lots'] else 'running',
            }
            _write_job(gateway, ubigeo, value)
            if progress:
                progress(ubigeo, value)
            if not status['pending_lots']:
                if ids:
                    _audit_job(gateway, ubigeo, ids, value)
                return
            if not advanced:
                raise ValueError('La migración no pudo avanzar; revisa los vectores archivados.')
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


def _run_all(actor, batch_size, job_id):
    gateway = Gateway()
    cloud = R2(timeout=20)
    stop_heartbeat = threading.Event()
    totals = {
        'processed_lots': 0,
        'linked_lots': 0,
        'pending_lots': 0,
        'source_lots': 0,
        'completed_districts': 0,
        'failed_districts': [],
    }

    def heartbeat():
        while not stop_heartbeat.wait(60):
            current = _read_job(gateway, ALL_SCOPE)
            if (current.get('id') != job_id or
                    current.get('status') != 'running'):
                return
            try:
                _write_job(gateway, ALL_SCOPE, current)
            except StorageError:
                return

    heartbeat_thread = threading.Thread(
        target=heartbeat,
        name='geollaqta-migration-all-heartbeat',
        daemon=True,
    )
    heartbeat_thread.start()
    try:
        from cuadrantizacion import geollaqta

        districts = sorted(geollaqta.DISTRICTS)
        for ubigeo in districts:
            ids, truncated = geollaqta_bulk.lot_ids(ubigeo, cloud)
            if truncated:
                totals['failed_districts'].append({
                    'ubigeo': ubigeo,
                    'error': 'El inventario R2 está truncado.',
                })
                continue
            if ids:
                totals['source_lots'] += len(ids)

        current = {
            **_read_job(gateway, ALL_SCOPE),
            **totals,
            'scope': ALL_SCOPE,
            'districts_total': len(districts),
            'districts_list': districts,
            'current_ubigeo': None,
            'current_district': None,
            'message': 'Preparando la migración de todos los distritos.',
            'status': 'running',
        }
        _write_job(gateway, ALL_SCOPE, current)

        for index, ubigeo in enumerate(districts, 1):
            if not _owns(gateway, ALL_SCOPE, job_id):
                return
            district_name = geollaqta.DISTRICTS[ubigeo]['name']
            current = {
                **_read_job(gateway, ALL_SCOPE),
                'current_ubigeo': ubigeo,
                'current_district': district_name,
                'message': (
                    'Migrando distrito %d de %d: %s.' %
                    (index, len(districts), district_name)),
            }
            _write_job(gateway, ALL_SCOPE, current)
            claimed, district_job = _claim(
                gateway, ubigeo, actor, batch_size)
            if not claimed:
                totals['failed_districts'].append({
                    'ubigeo': ubigeo,
                    'error': 'Ya existe una migración activa para el distrito.',
                })
                continue

            def progress(current_ubigeo, district_value):
                linked = totals['linked_lots'] + int(
                    district_value.get('linked_lots', 0))
                pending = totals['pending_lots'] + int(
                    district_value.get('pending_lots', 0))
                processed = totals['processed_lots'] + int(
                    district_value.get('processed_lots', 0))
                latest = _read_job(gateway, ALL_SCOPE)
                _write_job(gateway, ALL_SCOPE, {
                    **latest,
                    'current_ubigeo': current_ubigeo,
                    'processed_lots': processed,
                    'linked_lots': linked,
                    'pending_lots': pending,
                    'source_lots': totals['source_lots'],
                    'current_linked_lots': int(
                        district_value.get('linked_lots', 0)),
                    'current_pending_lots': int(
                        district_value.get('pending_lots', 0)),
                    'current_linked_total': linked,
                    'current_pending_total': pending,
                    'last_batch_revision': district_value.get(
                        'last_batch_revision'),
                    'message': latest.get('message'),
                })

            _run(
                ubigeo, actor, batch_size, district_job['id'],
                progress=progress,
            )
            finished = _read_job(gateway, ubigeo)
            totals['processed_lots'] += int(
                finished.get('processed_lots', 0))
            totals['linked_lots'] += int(
                finished.get('linked_lots', 0))
            totals['pending_lots'] += int(
                finished.get('pending_lots', 0))
            if finished.get('status') == 'done':
                totals['completed_districts'] += 1
            else:
                totals['failed_districts'].append({
                    'ubigeo': ubigeo,
                    'error': finished.get('message', 'No terminó.'),
                })
            current = {
                **_read_job(gateway, ALL_SCOPE),
                **totals,
                'current_ubigeo': ubigeo,
                'current_district': district_name,
                'last_batch_revision': finished.get(
                    'last_batch_revision'),
                'message': (
                    'Distrito %d de %d terminado: %s.' %
                    (index, len(districts), district_name)),
            }
            _write_job(gateway, ALL_SCOPE, current)

        final = {
            **_read_job(gateway, ALL_SCOPE),
            **totals,
            'current_ubigeo': None,
            'current_district': None,
            'status': (
                'done' if not totals['failed_districts'] and
                not totals['pending_lots'] else 'error'),
            'message': (
                'Migración global completa: %d distritos.' %
                totals['completed_districts']
                if not totals['failed_districts'] and
                not totals['pending_lots'] else
                'Migración global terminó con %d distritos fallidos y '
                '%d lotes pendientes.' % (
                    len(totals['failed_districts']),
                    totals['pending_lots'])),
            'retryable': bool(totals['failed_districts']),
        }
        _write_job(gateway, ALL_SCOPE, final)
    except Exception as error:
        current = _read_job(gateway, ALL_SCOPE)
        try:
            _write_job(gateway, ALL_SCOPE, {
                **current,
                **totals,
                'status': 'error',
                'message': str(error),
                'retryable': isinstance(error, (StorageError, OSError)),
            })
        except Exception:
            pass
    finally:
        stop_heartbeat.set()
        with _threads_lock:
            _threads.pop(ALL_SCOPE, None)
