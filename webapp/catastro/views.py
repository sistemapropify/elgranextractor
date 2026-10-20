import io
import json
import re
import os
import time
from functools import wraps
from pathlib import Path

from django.http import FileResponse, JsonResponse, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .jobs import start_job
from .state import State
from .storage import credentials, StorageError, R2
from scrapi.geollaqta_scraper import DISTRICTS, CATALOG


def admin_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        user = getattr(request, 'current_user', None) or getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', False):
            if request.path.startswith('/catastro/api/'):
                return JsonResponse({'error': 'Inicia sesión para administrar el catastro.'}, status=401)
            return redirect('/login/?next=/catastro/')
        if not (getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False)):
            return JsonResponse({'error': 'El archivo catastral requiere acceso de administrador.'}, status=403)
        if os.environ.get('CATASTRO_DISABLE_LOCAL_COLLECTION') == '1' and not request.path.startswith(('/catastro/visor-planos/', '/catastro/api/planos/', '/catastro/maestro/', '/catastro/api/maestro/')):
            return redirect('https://acm.propifai.com' + request.get_full_path())
        return view(request, *args, **kwargs)
    return wrapped


@require_GET
@admin_required
@ensure_csrf_cookie
def dashboard(request):
    return render(request, 'catastro/dashboard.html', {'districts': list(DISTRICTS.values())})


@require_GET
@admin_required
def status(request):
    ubigeo = request.GET.get('ubigeo') or None
    if ubigeo and ubigeo not in DISTRICTS:
        return JsonResponse({'error': 'Distrito no válido.'}, status=400)
    state = State()
    try:
        data = state.snapshot(ubigeo)
        presence = state.db.execute('SELECT heartbeat,source_status FROM collector_presence WHERE id=1').fetchone()
        data['collector'] = {'external': os.environ.get('CATASTRO_EXECUTION_MODE') == 'external',
                             'connected': bool(presence and presence[0] > time.time() - 60),
                             'source_status': presence[1] if presence else 'unchecked',
                             'hosted': os.environ.get('CATASTRO_AZURE_WORKER_ENABLED') == '1'}
        for job in data['jobs']:
            job['district_name'] = DISTRICTS.get(job['ubigeo'], {}).get('name', job['ubigeo'])
    finally:
        state.close()
    try:
        config = credentials()
        data['storage'] = {'configured': True, 'bucket': config['R2_BUCKET']}
    except StorageError:
        data['storage'] = {'configured': False, 'bucket': None}
    response = JsonResponse(data)
    response['Cache-Control'] = 'private, no-store'
    return response


@require_POST
@admin_required
def start(request):
    try:
        params = json.loads(request.body)
        if not isinstance(params, dict) or not isinstance(params.get('retry_missing', False), bool):
            raise ValueError('Parámetros no válidos.')
        job_id = start_job(params.get('ubigeo'), params.get('limit'), params.get('lot_id') or None,
                           params.get('retry_missing', False), workers=params.get('workers'))
        return JsonResponse({'job_id': job_id}, status=202)
    except (ValueError, TypeError, RuntimeError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)


@require_POST
@admin_required
def stop(request, job_id):
    state = State()
    try:
        job = state.job(job_id)
        if not job:
            return JsonResponse({'error': 'Ejecución no encontrada.'}, status=404)
        if job['status'] in ('queued', 'running'):
            state.update_job(job_id, stop=1, **({'status':'stopped','message':'Descarga detenida antes de comenzar.'} if job['status']=='queued' else {'message':'Pausa solicitada; terminando las solicitudes en curso y conservando el avance.'}))
        return JsonResponse({'stopping': True})
    finally:
        state.close()


def archived_manifest(state, row):
    path = state.root / row['ubigeo'] / row['lot_id'] / 'datos.json'
    if path.is_file():
        data = json.loads(path.read_text(encoding='utf-8'))
    elif row['uploaded']:
        body, _ = R2().get('geollaqta/' + row['ubigeo'] + '/' + row['lot_id'] + '/datos.json')
        data = json.loads(body)
    else:
        raise StorageError('El índice del predio está pendiente de almacenamiento.')
    if data.get('lot_id') != row['lot_id'] or data.get('district_ubigeo') != row['ubigeo']:
        # Accept older indexes without identifiers only from local files;
        # remote indexes must match their authenticated property route.
        if not path.is_file():
            raise StorageError('El índice archivado no corresponde al predio.')
    return data


@require_GET
@admin_required
def lot(request, lot_id):
    if not re.fullmatch(r'\d{14,18}', lot_id):
        return JsonResponse({'error': 'Lote no válido.'}, status=404)
    state = State()
    try:
        row = state.lot(lot_id)
        if not row:
            return JsonResponse({'error': 'Lote no archivado.'}, status=404)
        data = archived_manifest(state, row)
        files = [a for a in data['artifacts'] if a['type'] != 'source_html']
        return render(request, 'catastro/lot.html', {'lot_id': lot_id, 'data': data, 'files': files,
                                                     'district': DISTRICTS[row['ubigeo']]['name']})
    except StorageError as exc:
        return JsonResponse({'error': str(exc)}, status=502)
    finally:
        state.close()


@require_GET
@admin_required
def asset(request, lot_id, filename):
    if not re.fullmatch(r'\d{14,18}', lot_id) or not re.fullmatch(r'[A-Za-z0-9_.-]+', filename):
        return JsonResponse({'error': 'Archivo no válido.'}, status=404)
    state = State()
    try:
        row = state.lot(lot_id)
        if not row:
            return JsonResponse({'error': 'Lote no archivado.'}, status=404)
        folder = state.root / row['ubigeo'] / lot_id
        manifest = archived_manifest(state, row)
        entries = {a['filename']: a for a in manifest['artifacts']}
        if filename != 'datos.json' and filename not in entries:
            return JsonResponse({'error': 'Archivo no archivado.'}, status=404)
        path = folder / filename
        if path.is_file():
            stream = path.open('rb')
        elif row['uploaded']:
            body, _ = R2().get('geollaqta/' + row['ubigeo'] + '/' + lot_id + '/' + filename)
            stream = io.BytesIO(body)
        else:
            return JsonResponse({'error': 'Archivo pendiente.'}, status=404)
        mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                'pdf': 'application/pdf', 'json': 'application/json'}.get(filename.rsplit('.', 1)[-1], 'application/octet-stream')
        response = FileResponse(stream, content_type=mime, as_attachment=mime in ('application/octet-stream', 'application/json'), filename=filename)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except StorageError as exc:
        return JsonResponse({'error': str(exc)}, status=502)
    finally:
        state.close()


@require_GET
@admin_required
def document_page(request, lot_id, filename, page_number):
    """Render the archived PDF page with its original lines and layout."""
    if not re.fullmatch(r'\d{14,18}', lot_id) or not re.fullmatch(r'[A-Za-z0-9_.-]+\.pdf', filename):
        return JsonResponse({'error': 'Documento no válido.'}, status=404)
    state = State()
    try:
        row = state.lot(lot_id)
        if not row:
            return JsonResponse({'error': 'Lote no archivado.'}, status=404)
        folder = state.root / row['ubigeo'] / lot_id
        data = archived_manifest(state, row)
        if not any(a['filename'] == filename and a['type'].endswith('pdf') for a in data['artifacts']):
            return JsonResponse({'error': 'Documento no archivado.'}, status=404)
        path = folder / filename
        if path.is_file():
            body = path.read_bytes()
        elif row['uploaded']:
            body, _ = R2().get('geollaqta/' + row['ubigeo'] + '/' + lot_id + '/' + filename)
        else:
            return JsonResponse({'error': 'Documento pendiente.'}, status=404)
        import fitz
        with fitz.open(stream=body, filetype='pdf') as pdf:
            if not 1 <= page_number <= len(pdf):
                return JsonResponse({'error': 'Página no encontrada.'}, status=404)
            page = pdf[page_number - 1]
            scale = min(1.75, 2600 / max(page.rect.width, page.rect.height))
            png = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).tobytes('png')
        response = HttpResponse(png, content_type='image/png')
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except (StorageError, RuntimeError, ValueError):
        return JsonResponse({'error': 'No se pudo mostrar la página del documento original.'}, status=422)
    finally:
        state.close()
