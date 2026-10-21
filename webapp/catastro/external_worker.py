"""Outbound-only collector: dashboard controls jobs; originals go directly to R2."""
import json
import hashlib
import re
import sqlite3
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from .state import State
from .storage import NoRedirect, R2
from scrapi.geollaqta_scraper import collect, Stopped


class ControlError(RuntimeError):
    pass


class Control:
    def __init__(self, origin, token):
        parsed = urlsplit(origin)
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/') or not (
            parsed.scheme == 'https' and parsed.hostname == 'acm.propifai.com' or
            parsed.scheme == 'http' and parsed.hostname in ('localhost','127.0.0.1')):
            raise ValueError('Usa el dominio de Prometeo o la vista local.')
        if len(token) < 32:
            raise ValueError('Configura la credencial privada del recolector.')
        self.origin, self.token = origin.rstrip('/'), token
        self.opener = build_opener(NoRedirect())

    def call(self, action, payload=None, job=None, lease=None):
        path = 'claim/' if job is None else job+'/'+action+'/'
        headers = {'Authorization':'Bearer '+self.token,'Content-Type':'application/json'}
        if lease:
            headers['X-Catastro-Lease'] = lease
        request = Request(self.origin+'/catastro/api/worker/'+path, data=json.dumps(payload or {}).encode(),headers=headers)
        # Leased actions are upserts/readbacks and may safely be repeated.
        # Claim is not: a lost reply must never claim another job.
        attempts = 5 if job is not None and action != 'finish' else 1
        for attempt in range(attempts):
            try:
                with self.opener.open(request,timeout=25) as response:
                    if response.headers.get_content_type() != 'application/json':
                        raise ControlError('El dashboard no devolvió una respuesta válida.')
                    return json.loads(response.read(20_000_000))
            except HTTPError as error:
                if error.code == 409:
                    raise Stopped('La ejecución se detuvo o fue reemplazada. Avance conservado.') from None
                if error.code not in (408,429,500,502,503,504) or attempt == attempts-1:
                    raise ControlError('El dashboard respondió HTTP '+str(error.code)+'. Los archivos confirmados en R2 se conservan.') from None
            except (URLError, TimeoutError, OSError, ValueError):
                if attempt == attempts-1:
                    raise ControlError('No se pudo comunicar con el dashboard después de reintentar. Los archivos confirmados en R2 se conservan.') from None
            time.sleep(min(2 ** attempt, 10))


def seed_memory_index(state, cloud, key):
    """Read the retired index from R2 into RAM; no SQLite/temp file is created."""
    if not re.fullmatch(r'geollaqta/_ledger/local-retired-\d{8}-[a-f0-9]{64}\.sqlite3', key):
        raise ValueError('Índice remoto no válido.')
    body, _ = cloud.get(key)
    if hashlib.sha256(body).hexdigest() != key[-72:-8]:
        raise ValueError('El índice remoto no coincide con su hash.')
    # A frozen serialized WAL database has no sidecar. Its in-memory copy uses
    # the normal journal header; rows/pages and the remote original stay intact.
    snapshot = bytearray(body)
    snapshot[18:20] = b'\x01\x01'
    previous = sqlite3.connect(':memory:')
    try:
        previous.deserialize(bytes(snapshot))
        previous.execute('PRAGMA temp_store=MEMORY')
        if previous.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('El índice remoto requiere revisión.')
        for table in ('lots', 'uploads'):
            columns = [r[1] for r in state.db.execute('PRAGMA table_info('+table+')')]
            names = ','.join(columns)
            state.db.executemany('INSERT OR REPLACE INTO '+table+' ('+names+') VALUES ('+','.join('?' for _ in columns)+')',previous.execute('SELECT '+names+' FROM '+table))
        state.db.commit()
    finally:
        previous.close()


def run_once(control, root, source=None, cloud=None, memory_only=False, seed_index=None):
    reply = control.call('claim')
    job = reply.get('job')
    if not job:
        return None
    job_id, lease = job['id'], reply['lease']
    def api(action, payload=None):
        return control.call(action,payload,job_id,lease)
    state = State(memory=True) if memory_only else State(root)
    last_heartbeat = 0
    synced = {}
    prepared = False
    try:
        if memory_only and seed_index:
            cloud = cloud or R2()
            seed_memory_index(state, cloud, seed_index)
        after = ''
        while True:
            seed = api('seed',{'after':after})
            if seed.get('stop'):
                raise Stopped('Descarga detenida antes de comenzar.')
            for row in seed['lots']:
                local = state.lot(row['lot_id'])
                if not local or row['updated'] > local['updated']:
                    details = {k:row[k] for k in ('object_id','status','uploaded','missing','reports','photos','bytes','error')}
                    state.save_lot(row['lot_id'],row['ubigeo'],updated=row['updated'],commit=False,**details)
                synced[row['lot_id']] = row['updated']
            state.db.commit()
            after = seed.get('next_after')
            if not after:
                break
        watermark = 0

        def flush():
            nonlocal watermark
            rows = state.db.execute('SELECT * FROM lots WHERE ubigeo=? AND updated>? AND (? IS NULL OR lot_id=?) ORDER BY updated',
                                    (job['ubigeo'],watermark,job['lot_id'],job['lot_id'])).fetchall()
            for row in rows:
                if row['updated'] <= synced.get(row['lot_id'],0):
                    continue
                prefix = 'geollaqta/'+job['ubigeo']+'/'+row['lot_id']+'/'
                uploads = [dict(r) for r in state.db.execute('SELECT * FROM uploads WHERE object_key>=? AND object_key<?', (prefix,prefix+'\uffff'))]
                api('lot',{'lot':dict(row),'uploads':uploads})
                synced[row['lot_id']] = row['updated']
            if rows:
                watermark = rows[-1]['updated']

        def checkpoint():
            nonlocal last_heartbeat
            if time.monotonic()-last_heartbeat >= 5:
                try:
                    if api('heartbeat').get('stop'):
                        raise Stopped('Descarga detenida; avance conservado para reanudar.')
                except ControlError as error:
                    raise Stopped(str(error)) from None
                last_heartbeat = time.monotonic()

        def progress(data):
            flush()
            if api('progress',data).get('stop'):
                raise Stopped('Descarga detenida; avance conservado para reanudar.')

        prepared = True
        flush()  # Recover uploads acknowledged locally before a lost dashboard connection.
        result = collect(job['ubigeo'],job['limit_lots'] or None,lot_id=job['lot_id'],
                         retry_missing=bool(job['retry_missing']),root=root,source=source,r2=cloud,
                         progress=progress,checkpoint=checkpoint,keep_local=False,
                         workers=min(job.get('workers', 1),2) if memory_only else job.get('workers', 1),
                         **({'state':state} if memory_only else {}))
        flush()
        api('finish',{'status':'failed' if result['failed'] else 'completed',
                      'message':f"{result['processed']} lotes procesados; {result['uploaded']} archivados en R2; "
                                f"{result['remaining_objects']} por archivar; {result['partial']} con documentos pendientes."})
        return result
    except Stopped as error:
        try:
            if prepared:
                flush()
            api('finish',{'status':'stopped','message':str(error)})
        except (Stopped,ControlError):
            pass
        return {'stopped':True}
    except Exception as error:
        message = str(error) if isinstance(error,RuntimeError) else 'Error del recolector. Avance conservado para reanudar.'
        try:
            api('finish',{'status':'failed','message':message[:500]})
        except (Stopped,ControlError):
            pass
        raise
    finally:
        state.close()
