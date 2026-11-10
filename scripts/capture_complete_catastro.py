"""Archive every available COFOPRI expedient without on-demand retrieval."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(r'D:\PROMETEO\catastro_completo')
WORK.mkdir(parents=True, exist_ok=True)
os.environ['CATASTRO_DATA_DIR'] = str(WORK / 'trabajo')
os.environ['CATASTRO_STATE_DB'] = str(WORK / 'estado.sqlite3')
os.environ['CATASTRO_KEEP_LOCAL'] = '0'
os.environ['CATASTRO_MASTER_COLLECTION_ENABLED'] = '1'
os.environ['CATASTRO_MASTER_STORAGE'] = 'd1'
os.environ.setdefault('CATASTRO_REQUEST_INTERVAL', '0.05')
os.environ.setdefault('CATASTRO_MAX_WORKERS', '20')
os.environ.setdefault('CATASTRO_FORMALIZATION_WORKERS', '6')
sys.path.insert(0, str(ROOT / 'webapp'))

from django.conf import settings

if not settings.configured:
    settings.configure(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        },
    })

from catastro import cofopri_vector_migration, geollaqta_bulk, vector_snapshots
from catastro.formalization_detail_migration import (
    migrate_formalization_details,
)
from catastro.geollaqta_bulk import linked_lot_ids
from catastro.jobs import run_job, start_job
from catastro.master_d1 import Gateway
from catastro.manifest_migration import migrate_manifests_direct
from catastro.master_store import Conflict
from catastro.state import State
from catastro.storage import StorageError
from cuadrantizacion.geollaqta import DISTRICTS

INCREMENTAL_IMPORTED = {}
INCREMENTAL_FAILED = {}
FORMALIZATION_RECORDS = {}
REPORT_LOCK = threading.RLock()


def seed_existing(district):
    ids, truncated = geollaqta_bulk.lot_ids(district)
    object_by_lot = {}
    try:
        snapshot = vector_snapshots.read_snapshot(
            district, 'lotes', source='pcdpi')
        for feature in snapshot.get('features') or []:
            properties = feature.get('properties') or {}
            lot_id = str(properties.get('ID_LOTE') or '').strip()
            object_id = properties.get('OBJECTID')
            if (lot_id and type(object_id) is int and object_id > 0):
                object_by_lot[lot_id] = object_id
    except (ValueError, StorageError):
        pass
    state = State()
    try:
        for lot_id in ids:
            if state.lot(lot_id):
                continue
            state.save_lot(
                lot_id,
                district,
                object_id=object_by_lot.get(lot_id),
                # A prefix proves that something was uploaded, not that the
                # lot is complete. Verify it through the normal collector
                # before excluding it from the migration.
                status='failed',
                uploaded=1,
                missing=0,
                reports=0,
                photos=0,
                error='Archivo R2 pendiente de verificación y normalización.',
            )
    finally:
        state.close()
    return len(ids), truncated


def pcdpi_districts():
    return sorted({
        row['ubigeo'] for row in vector_snapshots.inventory()['snapshots']
        if (row.get('source') or 'pcdpi') == 'pcdpi'
    })


def write_report(report):
    with REPORT_LOCK:
        (WORK / 'captura_completa_resultado.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )


def capture_gallery_district(district, report, retry_missing=False):
    metadata = DISTRICTS[district]
    started = time.monotonic()
    imported = INCREMENTAL_IMPORTED.setdefault(district, set())
    imported.clear()
    failed = INCREMENTAL_FAILED.setdefault(district, set())
    failed.clear()
    stop_import = threading.Event()

    def import_while_capturing():
        gateway = Gateway()
        imported.update(linked_lot_ids(gateway, district))
        while not stop_import.wait(15):
            state = State()
            try:
                available = [
                    row['lot_id'] for row in state.db.execute(
                        '''SELECT lot_id FROM lots
                           WHERE ubigeo=? AND uploaded=1
                             AND status IN ('complete','partial')
                           ORDER BY lot_id''',
                        (district,),
                    )
                ]
            finally:
                state.close()
            pending = [lot_id for lot_id in available
                       if lot_id not in imported]
            offset = 0
            batch_size = 5
            while offset < len(pending):
                if stop_import.is_set():
                    return
                chunk = pending[offset:offset + batch_size]
                try:
                    migrate_manifests_direct(
                        gateway, district, metadata['name'], chunk,
                        actor='carga-completa-catastro-maestro')
                except StorageError as error:
                    print(
                        'IMPORT_INCREMENTAL_RETRY', district,
                        type(error).__name__, str(error), flush=True)
                    if error.http_status == 404:
                        match = re.search(
                            r'Lote\s+([A-Za-z0-9-]+):', str(error))
                        missing = [match.group(1)] if match else chunk
                        state = State()
                        try:
                            for lot_id in missing:
                                stored = state.lot(lot_id)
                                if stored:
                                    state.save_lot(
                                        lot_id, district,
                                        object_id=stored['object_id'],
                                        status='failed',
                                        uploaded=0,
                                        missing=0,
                                        reports=0,
                                        photos=0,
                                        error='Manifiesto R2 faltante; recapturar.',
                                    )
                        finally:
                            state.close()
                        failed.update(missing)
                        pending = [
                            lot_id for lot_id in pending
                            if lot_id not in set(missing)
                        ]
                        continue
                    if 'excede los límites' in str(error) and batch_size > 1:
                        batch_size = max(1, batch_size // 2)
                        continue
                    offset += len(chunk)
                    continue
                except Conflict as error:
                    print(
                        'IMPORT_INCREMENTAL_RETRY', district,
                        type(error).__name__, str(error), flush=True)
                    time.sleep(2)
                    continue
                except Exception as error:
                    print(
                        'IMPORT_INCREMENTAL_ERROR', district,
                        type(error).__name__, str(error), flush=True)
                    offset += len(chunk)
                    continue
                imported.update(chunk)
                offset += len(chunk)
                batch_size = 5
                print(
                    'IMPORT_INCREMENTAL', district, len(imported),
                    len(available), flush=True)

    importer = threading.Thread(
        target=import_while_capturing,
        name='catastro-d1-' + district,
        daemon=True,
    )
    importer.start()
    print('GALLERY_START', district, metadata['name'], flush=True)
    try:
        archived, truncated = seed_existing(district)
        state = State()
        try:
            for row in state.db.execute(
                    '''SELECT id FROM jobs
                       WHERE ubigeo=? AND status IN ('queued','running')''',
                    (district,)):
                state.update_job(
                    row['id'], status='stopped',
                    message='Reanudado por la carga completa del Catastro Maestro.')
        finally:
            state.close()
        job_id = start_job(
            district,
            launch=False,
            retry_missing=retry_missing,
            workers=int(os.environ['CATASTRO_MAX_WORKERS']),
        )
        result = run_job(job_id)
        report['gallery_results'].append({
            'ubigeo': district,
            'district': metadata['name'],
            'job_id': job_id,
            'existing_archive_prefixes': archived,
            'inventory_truncated': truncated,
            'result': result,
            'seconds': round(time.monotonic() - started, 1),
        })
        print(
            'GALLERY_DONE', district, json.dumps(result, ensure_ascii=False),
            flush=True,
        )
    except Exception as error:
        report['gallery_failures'].append({
            'ubigeo': district,
            'district': metadata['name'],
            'error': str(error),
        })
        print(
            'GALLERY_ERROR', district, type(error).__name__, str(error),
            flush=True,
        )
    finally:
        stop_import.set()
        importer.join(timeout=120)
        write_report(report)
    return bool(
        report['gallery_results']
        and report['gallery_results'][-1].get('ubigeo') == district
        and not report['gallery_results'][-1]['result'].get('failed')
        and not report['gallery_results'][-1]['result'].get('partial')
        and not report['gallery_results'][-1]['result'].get('remaining_objects')
        and not INCREMENTAL_FAILED.get(district)
    )


def import_gallery_district(district, report, skip=()):
    """Normalize every successfully archived manifest from one district into D1."""
    metadata = DISTRICTS[district]
    state = State()
    try:
        lots = [
            row['lot_id'] for row in state.db.execute(
                '''SELECT lot_id FROM lots
                   WHERE ubigeo=? AND uploaded=1
                     AND status IN ('complete','partial')
                   ORDER BY lot_id''',
                (district,),
            )
        ]
    finally:
        state.close()
    skipped = set(skip)
    lots = [lot_id for lot_id in lots if lot_id not in skipped]
    print(
        'IMPORT_START', district, len(lots),
        'incremental', len(skipped), flush=True)
    imported = failed = 0
    gateway = Gateway()
    offset = 0
    batch_size = 5
    while offset < len(lots):
        chunk = lots[offset:offset + batch_size]
        try:
            migrate_manifests_direct(
                gateway, district, metadata['name'], chunk,
                actor='carga-completa-catastro-maestro')
            imported += len(chunk)
            offset += len(chunk)
            batch_size = 5
        except Conflict:
            time.sleep(3)
            continue
        except StorageError as error:
            if 'excede los límites' in str(error) and batch_size > 1:
                batch_size = max(1, batch_size // 2)
                continue
            failed += len(chunk)
            report['d1_import_failures'].append({
                'ubigeo': district,
                'lots': chunk,
                'error': str(error),
            })
            offset += len(chunk)
        except Exception as error:
            failed += len(chunk)
            report['d1_import_failures'].append({
                'ubigeo': district,
                'lots': chunk,
                'error': str(error),
            })
            offset += len(chunk)
        if offset % 500 == 0 or offset >= len(lots):
            print(
                'IMPORT_PROGRESS', district, offset, len(lots),
                'failed', failed, flush=True)
            write_report(report)
    item = {
        'ubigeo': district,
        'district': metadata['name'],
        'available': len(lots),
        'already_imported_incrementally': len(skipped),
        'imported': imported,
        'failed': failed,
    }
    report['d1_import_results'].append(item)
    print('IMPORT_DONE', district, json.dumps(item, ensure_ascii=False),
          flush=True)
    write_report(report)


def capture_formalization_details(district, report):
    metadata = DISTRICTS[district]
    lots = cofopri_vector_migration.merged_formalization_lots(district)
    print(
        'FORMAL_START', district, metadata['name'], len(lots),
        flush=True,
    )
    started = time.monotonic()
    saved = failed = skipped = 0
    tasks = []
    records = []
    for lot in lots:
        properties = lot.get('properties') or {}
        predio = str(properties.get('ID_PREDIO_RPU') or lot.get('id') or '')
        object_id = properties.get('OBJECTID')
        if (not predio.startswith('P')
                or type(object_id) is not int or object_id <= 0):
            skipped += 1
            continue
        tasks.append((lot, lot['source'], predio, object_id))

    def load_detail(task):
        lot, source, predio, object_id = task
        try:
            value = vector_snapshots.formalization_detail(
                source, predio, object_id, district)
            if value.get('FORMALIZATION_DETAIL_STATUS') == 'available':
                key = value.get('PERSISTED_OBJECT_KEY')
                digest = value.get('PERSISTED_SHA256')
                if not key or not digest:
                    return task, 'No se pudo verificar el archivo R2', None
                detail = {
                    name: item for name, item in value.items()
                    if not name.startswith('PERSISTED_')
                }
                return task, None, (lot, detail, key, digest)
            return task, 'No devolvió datos', None
        except Exception as error:
            return task, str(error), None

    workers = min(
        len(tasks),
        int(os.environ.get('CATASTRO_FORMALIZATION_WORKERS', '12')),
    )
    pending = tasks
    failure_messages = {}
    for capture_attempt in range(6):
        if not pending:
            break
        next_pending = []
        with ThreadPoolExecutor(
                max_workers=max(1, min(workers, len(pending))),
                thread_name_prefix='formalizacion') as pool:
            futures = [pool.submit(load_detail, task) for task in pending]
            for index, future in enumerate(as_completed(futures), 1):
                task, error, record = future.result()
                lot, source, predio, object_id = task
                if error is None:
                    saved += 1
                    records.append(record)
                    failure_messages.pop(task, None)
                else:
                    next_pending.append(task)
                    failure_messages[task] = error
                if index % 100 == 0 or index == len(pending):
                    print(
                        'FORMAL_PROGRESS', district, index, len(pending),
                        'pass', capture_attempt + 1,
                        'saved', saved, 'pending', len(next_pending),
                        'skipped', skipped,
                        flush=True,
                    )
                    write_report(report)
        pending = next_pending
        if pending and capture_attempt < 5:
            delay = min(30 * (capture_attempt + 1), 180)
            print(
                'FORMAL_RETRY', district, capture_attempt + 1,
                'pending', len(pending), 'wait', delay, flush=True)
            time.sleep(delay)
    failed = len(pending)
    for task in pending:
        lot, source, predio, object_id = task
        report['formalization_detail_failures'].append({
            'ubigeo': district,
            'source': source,
            'predio': predio,
            'object_id': object_id,
            'error': failure_messages.get(task, 'No se pudo descargar'),
        })
    item = {
        'ubigeo': district,
        'district': metadata['name'],
        'available': len(lots),
        'saved': saved,
        'failed': failed,
        'skipped': skipped,
        'seconds': round(time.monotonic() - started, 1),
    }
    report['formalization_results'].append(item)
    FORMALIZATION_RECORDS[district] = records
    import_formalization_to_d1(district, lots, item, records)
    write_report(report)
    print('FORMAL_DONE', district, json.dumps(item), flush=True)


def import_formalization_to_d1(district, lots, item, records=None):
    metadata = DISTRICTS[district]
    last_error = None
    for attempt in range(5):
        try:
            imported = migrate_formalization_details(
                Gateway(), district, metadata['name'], lots,
                batch_size=5,
                actor='carga-completa-catastro-maestro',
                records=records)
            item['d1_import'] = {
                'available': imported.get('available', 0),
                'processed': imported.get('processed', 0),
            }
            item.pop('d1_import_error', None)
            return
        except Exception as error:
            last_error = error
            if attempt == 4:
                break
            delay = 30 * (2 ** attempt)
            print(
                'FORMAL_IMPORT_RETRY', district, attempt + 1,
                type(error).__name__, str(error),
                'wait', delay, flush=True)
            time.sleep(delay)
    item['d1_import_error'] = str(last_error)
    print(
        'FORMAL_IMPORT_ERROR', district,
        type(last_error).__name__, str(last_error), flush=True)


def retry_formalization_imports(report):
    failed_districts = {
        item['ubigeo'] for item in report['formalization_results']
        if item.get('d1_import_error')
    }
    for district in sorted(failed_districts):
        item = next(
            value for value in report['formalization_results']
            if value['ubigeo'] == district)
        try:
            lots = cofopri_vector_migration.merged_formalization_lots(
                district)
            import_formalization_to_d1(
                district, lots, item,
                FORMALIZATION_RECORDS.get(district))
        except Exception as error:
            item['d1_import_error'] = str(error)
        write_report(report)


def capture_all_formalization(report):
    for district in sorted(DISTRICTS):
        try:
            capture_formalization_details(district, report)
        except Exception as error:
            report['formalization_detail_failures'].append({
                'ubigeo': district,
                'district': DISTRICTS[district]['name'],
                'error': str(error),
            })
            print(
                'FORMAL_DISTRICT_ERROR', district,
                type(error).__name__, str(error), flush=True)
            write_report(report)
    retry_formalization_imports(report)


def main():
    report = {
        'started_at': int(time.time()),
        'gallery_results': [],
        'gallery_failures': [],
        'd1_import_results': [],
        'd1_import_failures': [],
        'formalization_results': [],
        'formalization_detail_failures': [],
    }
    formalization = threading.Thread(
        target=capture_all_formalization,
        args=(report,),
        name='catastro-formalizacion',
        daemon=False,
    )
    formalization.start()
    state = State()
    try:
        for row in state.db.execute(
                "SELECT id FROM jobs WHERE status IN ('queued','running')"):
            state.update_job(
                row['id'], status='stopped',
                message='Reanudado por la captura completa del catastro.')
    finally:
        state.close()
    districts = sorted(DISTRICTS)
    retry = list(districts)
    for attempt in range(4):
        retry_next = []
        for district in retry:
            local_attempt = 0
            previous_remaining = None
            stalled = 0
            while True:
                completed = capture_gallery_district(
                    district, report,
                    retry_missing=attempt > 0 or local_attempt > 0)
                if INCREMENTAL_FAILED.get(district):
                    report['d1_import_failures'].append({
                        'ubigeo': district,
                        'lots': sorted(INCREMENTAL_FAILED[district]),
                        'error': (
                            'Manifiestos R2 faltantes; '
                            'lotes marcados para recaptura.'),
                    })
                import_gallery_district(
                    district, report,
                    skip=INCREMENTAL_IMPORTED.get(district, ()))
                if completed:
                    break
                latest = next(
                    (value for value in reversed(report['gallery_results'])
                     if value.get('ubigeo') == district),
                    None)
                remaining = int(
                    (latest or {}).get('result', {}).get(
                        'remaining_objects', previous_remaining or 0))
                if previous_remaining is not None and remaining >= previous_remaining:
                    stalled += 1
                else:
                    stalled = 0
                previous_remaining = remaining
                if stalled >= 5:
                    retry_next.append(district)
                    break
                local_attempt += 1
                delay = min(30 * local_attempt, 180)
                print(
                    'GALLERY_RESUME', district, local_attempt,
                    'remaining', remaining, 'wait', delay, flush=True)
                time.sleep(delay)
        retry = retry_next
        if not retry:
            break
        print(
            'GALLERY_RETRY_PASS', attempt + 2, len(retry), retry,
            flush=True,
        )
        time.sleep(min(30 * (attempt + 1), 120))
    formalization.join()
    report['finished_at'] = int(time.time())
    write_report(report)
    print(
        'FINAL',
        json.dumps({
            'gallery_districts': len(report['gallery_results']),
            'gallery_failures': len(report['gallery_failures']),
            'd1_import_districts': len(report['d1_import_results']),
            'd1_import_failures': len(report['d1_import_failures']),
            'formalization_districts': len(report['formalization_results']),
            'formalization_detail_failures':
                len(report['formalization_detail_failures']),
        }),
        flush=True,
    )
    return 0 if not report['gallery_failures'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
