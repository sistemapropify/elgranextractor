"""Administrative source/version authoring, available only in the local preview."""
import json
import io

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, csrf_protect, ensure_csrf_cookie
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.views.decorators.http import require_GET

from .views import admin_required
from . import source_manager, master_pipeline, cad_reader
from .master_store import Conflict
from .storage import StorageError


def unavailable():
    return JsonResponse({'error': 'La gestión nueva de fuentes sólo está habilitada en la vista local.'}, status=404)


@require_GET
@admin_required
@ensure_csrf_cookie
def viewer(request):
    if not source_manager.enabled():
        return unavailable()
    response = render(request, 'catastro/fuentes.html',{'master_durable':source_manager.durable()})
    response['Cache-Control'] = 'private, no-store'
    return response


@require_GET
@admin_required
@ensure_csrf_cookie
def plans_dashboard(request):
    if not source_manager.enabled():
        return unavailable()
    response = render(request, 'catastro/planos_dashboard.html', {
        'master_durable': source_manager.durable(),
        'dwg_available': cad_reader.available(),
    })
    response['Cache-Control'] = 'private, no-store'
    return response


@require_GET
@admin_required
def plans_portfolio(request):
    """Bounded metadata-only inventory across every district in the master."""
    if not source_manager.enabled():
        return unavailable()
    try:
        store = source_manager.store()
        project_sql = '''SELECT p.id,p.name,p.ubigeo,p.expected_sheets,
            count(DISTINCT s.sheet_code) AS registered_sheets
            FROM projects p LEFT JOIN sources s ON s.project_id=p.id
            GROUP BY p.id ORDER BY p.ubigeo,p.name LIMIT 1000'''
        file_sql = '''SELECT s.id AS source_id,s.name AS source_name,s.ubigeo,s.sheet_code,s.role,
            p.name AS project_name,p.expected_sheets,v.id AS version_id,v.label,v.source_date,v.crs,
            v.georeferencing,v.original_name,v.digest,
            count(DISTINCT c.layer||':'||c.source_feature_id) AS elements,
            json_extract(v.payload,'$.version.vector_review') AS vector_review,
            json_extract(v.payload,'$.version.vector_artifacts') AS vector_artifacts,
            json_extract(v.payload,'$.version.original.name') AS original_name_payload,
            json_extract(v.payload,'$.version.original.object_key') AS original_object_key
            FROM sources s LEFT JOIN projects p ON p.id=s.project_id
            LEFT JOIN versions v ON v.source_id=s.id LEFT JOIN contributions c ON c.version_id=v.id
            GROUP BY s.id,v.id ORDER BY s.ubigeo,s.name,v.created_at LIMIT 5000'''
        active_sql = '''SELECT ubigeo,count(DISTINCT e.id) AS geometries FROM entities e
            JOIN selections s ON s.entity_id=e.id AND s.field='$geometry'
            WHERE e.kind IN ('lote','manzana') GROUP BY ubigeo LIMIT 1000'''
        if source_manager.durable():
            projects, rows, active = store.gateway.read_many([
                {'sql': project_sql, 'params': []}, {'sql': file_sql, 'params': []},
                {'sql': active_sql, 'params': []}])
        else:
            with store.lock:
                projects=[dict(row) for row in store.db.execute(project_sql)]
                rows=[dict(row) for row in store.db.execute(file_sql)]
                active=[dict(row) for row in store.db.execute(active_sql)]
        import json
        files=[]
        for row in rows:
            row=dict(row)
            for key in ('georeferencing','vector_review','vector_artifacts'):
                if isinstance(row.get(key),str):
                    try:row[key]=json.loads(row[key])
                    except ValueError:row[key]=None
            row['original_name']=row.pop('original_name_payload',None) or row.get('original_name')
            row['original_available']=bool(row.pop('original_object_key',None)) or (source_manager.has_pdf(row['version_id']) if row.get('version_id') else False)
            files.append(row)
        response=JsonResponse({'storage':'d1' if source_manager.durable() else 'memory',
            'projects':projects,'files':files,'active_by_district':active,
            'truncated':len(rows)>=5000,'pipeline':master_pipeline.status()})
        response['Cache-Control']='private, no-store'
        return response
    except StorageError as error:
        return JsonResponse({'error':str(error)},status=503)


@csrf_protect
@admin_required
def workspace(request):
    if not source_manager.enabled():
        return unavailable()
    response = None
    try:
        store = source_manager.store()
        if request.method == 'GET':
            if request.GET.get('view') == 'records':
                value = {'records': store.records({k:v for k,v in request.GET.items() if k != 'view'}),
                         'revision': store.revision}
            elif request.GET.get('view') == 'geometry':
                value = store.collection(request.GET.get('ubigeo', ''), request.GET.get('kind', 'lote'))
            elif request.GET.get('view') == 'entity':
                value = store.entity(request.GET.get('id',''))
            elif request.GET.get('view') == 'catalog':
                from . import master_catalog
                value = {'items': master_catalog.search(
                    store.db, {key: item for key, item in request.GET.items() if key != 'view'}),
                    'revision': store.revision}
            elif request.GET.get('view') == 'pdf_info':
                from .master_georeference import page_info
                body = source_manager.pdf(request.GET.get('id', ''))
                if body is None:
                    raise ValueError('PDF original no disponible.')
                value = page_info(body, int(request.GET.get('page', '1')))
            else:
                summary=store.summary(request.GET.get('ubigeo','040103')) if source_manager.durable() else store.summary()
                value = {**summary, 'pipeline': master_pipeline.status()}
                for source in value['sources']:
                    for version in source['versions']:
                        version['original_available'] = source_manager.has_pdf(version['id'])
                        payload=source_manager.version_payload(version['id'])
                        version['vector_review']=(payload or {}).get('version',{}).get('vector_review')
                        version['vector_artifacts']=(payload or {}).get('version',{}).get('vector_artifacts',{})
        elif request.method == 'POST':
            limit = 12 * 1024 * 1024
            if int(request.META.get('CONTENT_LENGTH') or 0) > limit:
                raise ValueError('Divide el aporte en versiones de hasta 12 MB.')
            body = request.read(limit + 1)
            if len(body) > limit:
                raise ValueError('Divide el aporte en versiones de hasta 12 MB.')
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError('Solicitud no válida.')
            actor = getattr(request, 'current_user', None) or request.user
            author = getattr(actor, 'username', '') or str(getattr(actor, 'pk', 'administrador'))
            action = payload.get('action')
            if action == 'stage':
                value = store.stage(payload.get('payload'), payload.get('revision'), author)
            elif action == 'preview':
                value = store.preview(payload.get('plan'))
            elif action == 'apply':
                value = store.apply(payload.get('plan'), payload.get('token'), author)
            elif action == 'restore':
                value = store.restore(payload.get('target_revision'), payload.get('revision'), author, payload.get('reason'))
            elif action in ('calibrate', 'stage_calibration'):
                value = calibration(payload, author)
            else:
                raise ValueError('Acción no disponible.')
        else:
            return JsonResponse({'error': 'Método no permitido.'}, status=405)
        response = JsonResponse(value, json_dumps_params={'ensure_ascii': False})
    except Conflict as error:
        response = JsonResponse({'error': str(error)}, status=409)
    except StorageError as error:
        response = JsonResponse({'error':str(error)},status=503)
    except (ValueError, TypeError, KeyError) as error:
        response = JsonResponse({'error': str(error) if isinstance(error, ValueError)
                                 else 'Revisa el formato de la solicitud.'}, status=400)
    response['Cache-Control'] = 'private, no-store'
    return response


def calibration(payload, author):
    """Always recompute from the original; never accept client-supplied matrices."""
    from .master_georeference import calibrate, report_token
    from copy import deepcopy
    version_id = payload.get('version_id')
    if not isinstance(version_id, str):
        raise ValueError('Selecciona una versión PDF.')
    original = source_manager.version_payload(version_id)
    body = source_manager.pdf(version_id) if original else None
    if body is None:
        raise ValueError('El PDF original no está disponible.')
    report = calibrate(body, payload.get('controls'))
    if original['version'].get('original', {}).get('sha256') != report['page']['original_sha256']:
        raise ValueError('La huella del PDF no coincide con la versión elegida.')
    token = report_token(version_id, report)
    if payload['action'] == 'calibrate':
        return {'report': report, 'token': token}
    if token != payload.get('token'):
        raise Conflict('Los controles cambiaron. Calcula y revisa el informe otra vez.')
    if not report['within_tolerance']:
        raise ValueError('La propuesta excede la tolerancia indicada. Revisa los controles antes de registrarla.')
    candidate = {'source': deepcopy(original['source']),
                 'version': {'id': 'calibracion:' + token[:40], 'label': 'Calibración ' + token[:12],
                    'source_date': original['version'].get('source_date'), 'crs': None,
                    'original': deepcopy(original['version']['original']),
                    'georeferencing': {'status': 'pending', 'method': report['method'],
                                      'parent_version_id': version_id, 'calibration': report}},
                 'features': []}
    result = source_manager.store().stage(candidate, payload.get('revision'), author)
    # RAM previews have no R2 fallback. This retains bytes, never writes a temp file.
    if not source_manager.durable():
        source_manager.retain_pdf(candidate['version']['id'], body)
    return {**result, 'version_id': candidate['version']['id'],
            'notice': 'Propuesta de calibración registrada. Posición pendiente de revisión; no se activaron geometrías.'}


class MemoryPDFUpload(FileUploadHandler):
    """No fallback to Django's disk-backed temporary upload handler."""
    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.file = io.BytesIO()

    def receive_data_chunk(self, raw_data, start):
        if start + len(raw_data) > 12 * 1024 * 1024:
            raise StopUpload(connection_reset=True)
        self.file.write(raw_data)

    def file_complete(self, file_size):
        self.file.seek(0)
        return InMemoryUploadedFile(self.file, self.field_name, self.file_name,
                                    self.content_type, file_size, self.charset)


@csrf_exempt
@admin_required
def register_pdf(request):
    if not source_manager.enabled():
        return unavailable()
    request.upload_handlers = [MemoryPDFUpload(request)]
    return _register_pdf(request)


@csrf_protect
@admin_required
def vectorize_pdf(request, version_id):
    if not source_manager.enabled():
        return unavailable()
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    try:
        actor = getattr(request, 'current_user', None) or request.user
        from . import pdf_vectorize
        value = pdf_vectorize.stage(version_id, getattr(actor, 'username', '') or str(getattr(actor, 'pk', 'administrador')))
        value['notice'] = ('Trazos y texto extraídos a puntos locales del PDF y archivados en R2. '
                           'No se identificaron lotes ni se publicaron geometrías.')
        response = JsonResponse(value)
    except (ValueError, TypeError, KeyError) as error:
        response = JsonResponse({'error': str(error)}, status=400)
    except Conflict as error:
        response = JsonResponse({'error': str(error)}, status=409)
    except StorageError as error:
        response = JsonResponse({'error': str(error)}, status=503)
    response['Cache-Control'] = 'private, no-store'
    return response


@csrf_protect
def _register_pdf(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    try:
        upload = request.FILES.get('document')
        if upload is None or not 0 < upload.size <= 12 * 1024 * 1024:
            raise ValueError('Selecciona un PDF de hasta 12 MB.')
        # Django must retain this upload in RAM too; reject disk-backed uploads.
        if hasattr(upload, 'temporary_file_path'):
            raise ValueError('El PDF debe procesarse en memoria.')
        body = upload.read()
        from .pdf_inspection import inspect
        inspection = inspect(body)
        pages, layers = inspection['pages'], inspection['layers']
        metadata = json.loads(request.POST.get('metadata', '{}'))
        if not isinstance(metadata, dict):
            raise ValueError('Metadatos no válidos.')
        source_id = metadata.get('source_id')
        version_id = metadata.get('version_id')
        payload = {'source': {'id': source_id, 'name': metadata.get('name'), 'ubigeo': metadata.get('ubigeo'),
                   'project_id': metadata.get('project_id') or None, 'sheet_code': metadata.get('sheet_code') or None},
                   'version': {'id': version_id, 'label': metadata.get('label'),
                       'source_date': metadata.get('source_date') or None,
                       'crs': None, 'georeferencing': {'status': 'pending'},
                       'original': {'name': upload.name, 'sha256': inspection['sha256'],
                                    'pages': pages, 'layers': layers, 'archive_status': 'not_uploaded'}},
                   'features': [], 'inspection': {'pages': pages, 'layers': layers}}
        actor = getattr(request, 'current_user', None) or request.user
        value = source_manager.stage_pdf(payload, metadata.get('revision'),
                    getattr(actor, 'username', '') or str(getattr(actor, 'pk', 'administrador')), body)
        vectorization = None
        vectorization_error = None
        try:
            from . import pdf_vectorize
            vectorization = pdf_vectorize.stage(version_id,
                getattr(actor, 'username', '') or str(getattr(actor, 'pk', 'administrador')))
        except (ValueError, TypeError, KeyError, StorageError) as error:
            # The immutable source version is already registered; keep it visible
            # even when this PDF needs splitting or a derived-file retry.
            vectorization_error = str(error)
        notice = ('PDF y vectores fuente guardados en R2; versión registrada en D1. ' if source_manager.durable()
                  else 'PDF y versión registrados en el borrador local. ')
        notice += ('Trazos/texto extraídos a coordenadas locales; sin lotes homologados ni geometrías publicadas.'
                   if vectorization else 'La extracción automática quedó pendiente: '+(vectorization_error or 'reintenta desde el dashboard.'))
        response = JsonResponse({**value, 'inspection': payload['inspection'],
                                 'vectorization':vectorization, 'vectorization_error':vectorization_error,
                                 'notice':notice})
    except Conflict as error:
        response = JsonResponse({'error': str(error)}, status=409)
    except StorageError as error:
        response = JsonResponse({'error':str(error)},status=503)
    except (ValueError, TypeError, KeyError) as error:
        response = JsonResponse({'error': str(error) if isinstance(error, ValueError)
                                 else 'Revisa los datos de la lámina.'}, status=400)
    response['Cache-Control'] = 'private, no-store'
    return response


@require_GET
@admin_required
def pdf_page(request, version_id):
    if not source_manager.enabled():
        return unavailable()
    try:
        body = source_manager.pdf(version_id)
    except StorageError as error:
        return JsonResponse({'error':str(error)},status=503)
    if body is None:
        return JsonResponse({'error':'El original no está disponible en la memoria de este borrador.'},status=404)
    try:
        page = int(request.GET.get('page','1'))
        import fitz
        with fitz.open(stream=body,filetype='pdf') as document:
            if not 1 <= page <= len(document):
                raise ValueError('Página no disponible.')
            sheet = document[page-1]
            scale = min(2., 2400/max(sheet.rect.width,sheet.rect.height))
            response = HttpResponse(sheet.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).tobytes('png'),content_type='image/png')
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except (ValueError, TypeError):
        return JsonResponse({'error':'Página no válida.'},status=400)


@require_GET
@admin_required
def original_pdf(request,version_id):
    if not source_manager.enabled():return unavailable()
    try:
        body=source_manager.pdf(version_id)
        if body is None:return JsonResponse({'error':'Original no disponible.'},status=404)
        response=HttpResponse(body,content_type='application/pdf')
        response['Content-Disposition']='inline; filename="plano-original.pdf"'
        response['Cache-Control']='private, no-store'
        response['X-Content-Type-Options']='nosniff'
        return response
    except StorageError as error:return JsonResponse({'error':str(error)},status=503)


@require_GET
@admin_required
def vector_asset(request,version_id,filename):
    if not source_manager.enabled():return unavailable()
    try:
        from .master_vector_assets import retrieve
        body,mime=retrieve(version_id,filename)
        response=HttpResponse(body,content_type=mime)
        response['Cache-Control']='private, no-store'
        response['X-Content-Type-Options']='nosniff'
        response['Referrer-Policy']='no-referrer'
        if mime.startswith('text/html'):
            import re,base64,hashlib
            scripts=re.findall(rb'<script>(.*?)</script>',body,re.S)
            # HTML parsing normalizes Windows CRLF/CR to LF before CSP hashing.
            hashes=' '.join("'sha256-"+base64.b64encode(hashlib.sha256(s.replace(b'\r\n',b'\n').replace(b'\r',b'\n')).digest()).decode()+"'" for s in scripts)
            response['Content-Security-Policy']="default-src 'none'; style-src 'unsafe-inline'; script-src "+hashes+"; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
        else:
            response['Content-Disposition']='attachment; filename="'+filename+'"'
        return response
    except StorageError as error:return JsonResponse({'error':str(error)},status=503)
    except ValueError as error:return JsonResponse({'error':str(error)},status=404)


@require_GET
@admin_required
def medium(request,media_id):
    if not source_manager.enabled():return unavailable()
    try:
        from .storage import R2
        import hashlib
        item=source_manager.store().medium(media_id)
        key=item['object_key']
        if not key.startswith('geollaqta/') or '..' in key.split('/'):
            raise ValueError('Ruta de archivo no válida.')
        body,_=R2().get(key)
        if item['sha256'] and hashlib.sha256(body).hexdigest()!=item['sha256']:
            raise StorageError('El archivo no coincide con la huella registrada.')
        mime=('application/pdf' if body.startswith(b'%PDF-') else 'image/jpeg' if body.startswith(b'\xff\xd8\xff')
              else 'image/png' if body.startswith(b'\x89PNG\r\n\x1a\n') else None)
        if not mime:raise ValueError('Formato de archivo no disponible para visualización.')
        response=HttpResponse(body,content_type=mime)
        response['Content-Disposition']='inline; filename="'+media_id+('.pdf' if mime=='application/pdf' else '.jpg' if mime=='image/jpeg' else '.png')+'"'
        response['Cache-Control']='private, no-store';response['X-Content-Type-Options']='nosniff'
        return response
    except StorageError as error:return JsonResponse({'error':str(error)},status=503)
    except ValueError as error:return JsonResponse({'error':str(error)},status=404)
