"""One bounded collector process at a time, shared by dashboard and skill."""
import os
from pathlib import Path
import subprocess
import sys

from .state import State, ROOT
from .storage import credentials
from scrapi.geollaqta_scraper import collect, validate, Stopped


def start_job(ubigeo, limit=10, lot_id=None, retry_missing=False, launch=True):
    validate(ubigeo, limit, lot_id)
    credentials()  # Fail before queuing when this machine has no R2 configuration.
    state = State()
    try:
        job_id = state.create_job(ubigeo, int(limit), lot_id, retry_missing)
        if launch:
            command = [sys.executable, str(ROOT / 'scripts/collect_geollaqta.py'), '--job-id', job_id]
            try:
                kwargs = {'cwd': str(ROOT), 'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL,
                          'stderr': subprocess.DEVNULL, 'close_fds': True}
                if os.name == 'nt':
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                else:
                    kwargs['start_new_session'] = True
                process = subprocess.Popen(command, **kwargs)
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
            state.update_job(job_id, processed=data['processed'], message=data['message'])

        result = collect(job['ubigeo'], job['limit_lots'], lot_id=job['lot_id'],
                         retry_missing=bool(job['retry_missing']), progress=progress, checkpoint=checkpoint)
        remaining = result['remaining_objects']
        next_step = (f"Quedan {remaining} registros del inventario; inicia otra descarga para continuar."
                     if remaining else "Inventario consultado archivado; los documentos pendientes pueden reintentarse."
                     if result['partial'] or not result['complete'] else "Descarga completa para el ámbito seleccionado.")
        state.update_job(job_id, status='failed' if result['failed'] else 'completed',
                         processed=result['processed'],
                         message=f"{result['processed']} lotes procesados; {result['uploaded']} archivados en R2; "
                                 f"{result['partial']} con documentos pendientes; {result['failed']} con errores. {next_step}")
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
