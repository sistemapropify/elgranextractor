"""One resumable district collection at a time, shared by dashboard and skill."""
import os
from pathlib import Path
import subprocess
import sys
import time

from .state import State, ROOT
from .storage import credentials
from .parallel import worker_count
from scrapi.geollaqta_scraper import collect, validate, Stopped, CollectionError


def _connection_failure(message):
    return ('No se pudo conectar con COFOPRI.' in message
            or 'No se pudo conectar con R2;' in message)


def _wait_before_retry(seconds, checkpoint):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        checkpoint()
        time.sleep(min(1, max(0, until - time.monotonic())))


def collect_with_recovery(job, state, progress, checkpoint):
    """Resume only transport failures; access denials and damaged ledgers stop."""
    totals = {'processed': 0, 'uploaded': 0, 'partial': 0}
    def update(data):
        progress({**data, 'processed': totals['processed'] + data['processed']})
    for attempt in range(4):
        result = None
        try:
            result = collect(job['ubigeo'], job['limit_lots'] or None, lot_id=job['lot_id'],
                             retry_missing=bool(job['retry_missing']), progress=update,
                             checkpoint=checkpoint, workers=job['workers'])
            reason = str(result.get('last_error') or '')
        except CollectionError as exc:
            reason = str(exc)
            if not _connection_failure(reason) or attempt == 3:
                raise
        recoverable = all(_connection_failure(str(error)) for error in (result or {}).get('fatal_errors', [reason]))
        if result is not None and (not result['failed'] or not recoverable or attempt == 3):
            for key in totals:
                result[key] += totals[key]
            return result
        if result is not None:
            for key in totals:
                totals[key] += result[key]
        delay = 30 * (2 ** attempt)
        state.update_job(job['id'], message=(
            f'Conexión interrumpida. Reintentando en {delay} s '
            f'({attempt + 1}/3); se conserva y omite lo ya archivado.'))
        _wait_before_retry(delay, checkpoint)


def start_job(ubigeo, limit=None, lot_id=None, retry_missing=False, launch=True, workers=None):
    from .master_pipeline import require_collection_ready
    require_collection_ready()
    if os.environ.get('CATASTRO_DISABLE_LOCAL_COLLECTION') == '1':
        raise ValueError('La descarga en esta computadora está desactivada. Usa el recolector de producción en https://acm.propifai.com/catastro/.')
    validate(ubigeo, limit, lot_id)
    workers = worker_count(workers)
    credentials()  # Fail before queuing when this machine has no R2 configuration.
    executor = os.environ.get('CATASTRO_EXECUTION_MODE', 'server')
    if executor not in ('server', 'external'):
        raise ValueError('Modo de recolector no válido.')
    if executor == 'external':
        from .worker_api import worker_token
        if not worker_token():
            raise ValueError('El recolector externo está pendiente de configuración.')
    state = State()
    try:
        job_id = state.create_job(ubigeo, int(limit) if limit is not None else 0, lot_id, retry_missing, executor=executor, workers=workers)
        if executor == 'external':
            state.update_job(job_id, message='Esperando conexión del recolector. La descarga comenzará cuando esté disponible.')
        if launch and executor == 'server':
            command = [sys.executable, str(ROOT / 'scripts/collect_geollaqta.py'), '--job-id', job_id]
            try:
                log_dir = state.root / 'job-logs'
                log_dir.mkdir(exist_ok=True)
                kwargs = {'cwd': str(ROOT), 'stdin': subprocess.DEVNULL,
                          'stderr': subprocess.STDOUT, 'close_fds': True}
                working_root = os.environ.get('CATASTRO_COLLECTOR_DATA_DIR')
                if working_root:
                    # Working PDFs may use another drive; share the exact same
                    # ledger so archived lots are never rediscovered as new.
                    database = state.db.execute('PRAGMA database_list').fetchone()[2]
                    kwargs['env'] = {**os.environ, 'CATASTRO_DATA_DIR': working_root,
                                     'CATASTRO_STATE_DB': str(Path(database).resolve()),
                                     'CATASTRO_KEEP_LOCAL': '0'}
                if os.name == 'nt':
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                else:
                    kwargs['start_new_session'] = True
                with (log_dir / (job_id + '.log')).open('ab') as output:
                    process = subprocess.Popen(command, stdout=output, **kwargs)
                state.update_job(job_id, pid=process.pid)
            except OSError:
                state.update_job(job_id, status='failed', message='No se pudo iniciar el proceso de descarga.')
                raise ValueError('No se pudo iniciar el recolector.') from None
        return job_id
    finally:
        state.close()


def run_job(job_id):
    state = State()
    job = state.job(job_id)
    if not job:
        state.close()
        raise ValueError('Ejecución no encontrada.')
    if job['executor'] == 'external':
        state.close()
        raise ValueError('Esta ejecución debe atenderla el recolector externo.')
    claimed = state.db.execute("UPDATE jobs SET status='running' WHERE id=? AND status='queued'", (job_id,)).rowcount
    state.db.commit()
    if not claimed:
        state.close()
        raise ValueError('La ejecución ya fue iniciada o terminó.')
    try:
        def checkpoint():
            current = state.job(job_id)
            if current['stop'] or current['status'] != 'running':
                raise Stopped('Descarga detenida; se conservan los archivos para reanudar.')
            state.update_job(job_id)

        def progress(data):
            state.update_job(job_id, processed=data['processed'], message=data['message'],
                             source_objects=data.get('source_objects', 0), skipped_objects=data['skipped'],
                             selected_objects=data.get('selected_objects', 0), remaining_objects=data.get('remaining_objects', 0))

        result = collect_with_recovery(job, state, progress, checkpoint)
        remaining = result['remaining_objects']
        next_step = (f"Quedan {remaining} registros sin archivar; puedes reanudar desde el avance guardado."
                     if remaining else "Inventario consultado archivado; los documentos pendientes pueden reintentarse."
                     if result['partial'] or not result['complete'] else "Descarga completa para el ámbito seleccionado.")
        state.update_job(job_id, status='failed' if result['failed'] else 'completed',
                         processed=result['processed'], remaining_objects=remaining,
                         message=f"{result['processed']} lotes procesados; {result['uploaded']} archivados en R2; "
                                 f"{result['partial']} con documentos pendientes; {result['failed']} con errores. "
                                 f"{result.get('last_error', '')} {next_step}")
        return result
    except Stopped as exc:
        state.update_job(job_id, status='stopped', message=str(exc))
        return {'stopped': True}
    except Exception as exc:
        # Do not persist traceback, credentials, URLs or response bodies.
        safe = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else 'Error del recolector; revisa la configuración y reanuda.'
        state.update_job(job_id, status='failed', message=safe[:500])
        raise
    finally:
        state.close()
