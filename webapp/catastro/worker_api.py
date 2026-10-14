"""Private, leased collector control. No document bytes or R2 secrets cross this API."""
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import time
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .state import State


def worker_token():
    value = os.environ.get('CATASTRO_WORKER_TOKEN', '')
    if not value:
        path = Path(os.environ.get('CATASTRO_WORKER_TOKEN_FILE', str(Path.home()/'.codex/secrets/prometeo-catastro-worker.token')))
        if path.is_file():
            value = path.read_text().strip()
    return value if len(value) >= 32 else ''


def private_worker(view):
    @csrf_exempt
    @require_POST
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        token = worker_token()
        if os.environ.get('CATASTRO_EXECUTION_MODE') != 'external' or not token or not hmac.compare_digest(request.headers.get('Authorization', '').encode(), ('Bearer '+token).encode()):
            return JsonResponse({'error':'Acceso no autorizado.'}, status=403)
        if int(request.META.get('CONTENT_LENGTH') or 0) > 1_000_000:
            return JsonResponse({'error':'Solicitud demasiado grande.'}, status=413)
        try:
            data = json.loads(request.body or b'{}')
            if not isinstance(data, dict):
                raise ValueError()
            response = view(request, data, *args, **kwargs)
        except (ValueError, TypeError, KeyError):
            response = JsonResponse({'error':'Datos del recolector no válidos.'}, status=400)
        response['Cache-Control'] = 'private, no-store'
        return response
    return wrapped


@private_worker
def claim(request, data):
    source_status = data.get('source_status','available')
    may_claim = data.get('claim',True)
    if source_status not in ('unchecked','available','unavailable') or not isinstance(may_claim,bool):
        raise ValueError()
    state = State()
    try:
        state.db.execute('BEGIN IMMEDIATE')
        state.db.execute('INSERT OR REPLACE INTO collector_presence (id,heartbeat,source_status) VALUES (1,?,?)', (time.time(),source_status))
        row = state.db.execute("SELECT * FROM jobs WHERE executor='external' AND status='queued' AND stop=0 ORDER BY created LIMIT 1").fetchone()
        if not row or not may_claim or source_status != 'available':
            if row and source_status == 'unavailable':
                state.db.execute('UPDATE jobs SET message=?,heartbeat=? WHERE id=?',
                                 ('COFOPRI no responde. El recolector reintentará automáticamente; avance conservado.',time.time(),row['id']))
            state.db.commit()
            return JsonResponse({'job':None,'pending':bool(row)})
        lease = secrets.token_hex(32)
        state.db.execute("UPDATE jobs SET status='running',lease=?,heartbeat=?,message=? WHERE id=?",
                         (lease,time.time(),'Recolector conectado. Consultando inventario de COFOPRI.',row['id']))
        state.db.commit()
        job = {k:row[k] for k in ('id','ubigeo','limit_lots','lot_id','retry_missing')}
        return JsonResponse({'job':job,'lease':lease})
    finally:
        state.close()


def count(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10**12:
        raise ValueError()
    return value


@private_worker
def job_action(request, data, job_id, action):
    state = State()
    try:
        state.db.execute('BEGIN IMMEDIATE')
        job = state.job(job_id)
        if not job or job['executor'] != 'external' or job['status'] != 'running' or not job['lease'] or not hmac.compare_digest(job['lease'],request.headers.get('X-Catastro-Lease','')):
            return JsonResponse({'error':'La ejecución ya no pertenece a este recolector.'},status=409)
        if action == 'seed':
            after = str(data.get('after',''))
            if after and not re.fullmatch(job['ubigeo']+r'\d{8,12}',after):
                raise ValueError()
            rows = [dict(r) for r in state.db.execute('SELECT * FROM lots WHERE ubigeo=? AND lot_id>? AND (? IS NULL OR lot_id=?) ORDER BY lot_id LIMIT 500',
                                                    (job['ubigeo'],after,job['lot_id'],job['lot_id']))]
            state.update_job(job_id)
            return JsonResponse({'lots':rows,'next_after':rows[-1]['lot_id'] if len(rows)==500 else None,'stop':bool(job['stop'])})
        if action not in ('heartbeat','progress','lot','finish'):
            return JsonResponse({'error':'Acción no válida.'},status=404)
        values = {}
        if action == 'progress':
            for key in ('processed','source_objects','skipped_objects','selected_objects','remaining_objects'):
                if key in data:
                    values[key] = count(data[key])
            values['message'] = str(data.get('message',''))[:500]
        elif action == 'lot':
            row = data['lot']
            lot = str(row['lot_id'])
            if not re.fullmatch(job['ubigeo']+r'\d{8,12}',lot) or row['ubigeo'] != job['ubigeo'] or (job['lot_id'] and lot != job['lot_id']):
                raise ValueError()
            if row['status'] not in ('complete','partial','failed') or row['uploaded'] not in (0,1):
                raise ValueError()
            uploads = data.get('uploads',[])
            if len(uploads) > 1500:
                raise ValueError()
            # Validate everything before either the lot or upload ledger changes.
            for item in uploads:
                key = item['object_key']
                if not key.startswith('geollaqta/'+job['ubigeo']+'/'+lot+'/') or '..' in key.split('/') or not re.fullmatch(r'[a-f0-9]{64}',item['sha256']):
                    raise ValueError()
                count(item['bytes'])
            details = {k:count(row[k]) for k in ('object_id','uploaded','missing','reports','photos','bytes')}
            state.save_lot(lot,job['ubigeo'],commit=False,status=row['status'],error=str(row.get('error',''))[:500],**details)
            for item in uploads:
                state.save_upload(item['object_key'],item['sha256'],item['bytes'],commit=False)
        elif action == 'finish':
            if data['status'] not in ('completed','failed','stopped'):
                raise ValueError()
            values.update(status='stopped' if job['stop'] else data['status'],message=str(data.get('message',''))[:500])
        if action != 'finish' and job['stop']:
            # Final in-flight archive may be acknowledged, then collector stops.
            values['message'] = 'Detención solicitada; conservando el avance.'
        state.db.execute('UPDATE collector_presence SET heartbeat=? WHERE id=1',(time.time(),))
        state.update_job(job_id,**values)
        return JsonResponse({'stop':bool(job['stop'])})
    finally:
        state.close()
