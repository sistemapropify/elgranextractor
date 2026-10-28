"""ACM facade for the shared master; enforce the active role on every request."""
import io
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_GET
from .access import required
from catastro import master
from catastro import master_dossier
from catastro import raster_overlays, source_manager
from catastro.storage import StorageError


@require_GET
@required('cadastral_info')
def configuration(request):
    try:
        response = JsonResponse(master.configuration())
        response['Cache-Control'] = 'private, no-store'
        return response
    except StorageError:
        return JsonResponse({'error': 'No se pudo consultar la versión compartida del plano. Vuelve a consultar.'}, status=503)


@require_GET
@required('cadastral_info')
def raster_catalog(request):
    """ACM authentication adapter over the single Catastro Maestro catalog."""
    try:
        if not (source_manager.enabled() or source_manager.durable()):
            return JsonResponse({'overlays': [], 'revision': 0})
        store = source_manager.store()
        overlays = raster_overlays.list_all_overlays(store)
        for item in overlays:
            item['image_url'] = ('/acm/catastro/raster/' + item['id'] +
                                 '/imagen/?ubigeo=' + item['ubigeo'])
        response = JsonResponse({'overlays': overlays, 'revision': store.revision},
                                json_dumps_params={'ensure_ascii': False})
        response['Cache-Control'] = 'private, no-store'
        return response
    except StorageError:
        return JsonResponse({'error': 'No se pudo consultar el mosaico satelital.'}, status=503)


@require_GET
@required('cadastral_info')
def raster_image(request, overlay_id):
    try:
        if not (source_manager.enabled() or source_manager.durable()):
            raise ValueError('La capa satelital no está disponible.')
        body, content_type = raster_overlays.image_body(
            source_manager.store(), overlay_id, request.GET.get('ubigeo', ''))
        response = HttpResponse(body, content_type=content_type)
        response['Cache-Control'] = 'private, max-age=3600'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except StorageError:
        return JsonResponse({'error': 'No se pudo recuperar la imagen satelital.'}, status=503)
    except (ValueError, TypeError, KeyError):
        raise Http404


@require_GET
@required('cadastral_info')
def master_medium(request, media_id):
    """Serve a verified R2 original linked to a Catastro Maestro entity."""
    try:
        body, mime = _master_medium_body(media_id)
        response = HttpResponse(body, content_type=mime)
        response['Content-Disposition'] = 'inline'
        response['Cache-Control'] = 'private, max-age=3600'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except StorageError:
        return JsonResponse({'error': 'El archivo del Catastro Maestro no está disponible.'}, status=503)
    except (ValueError, KeyError):
        raise Http404


def _master_medium_body(media_id):
    if not (source_manager.enabled() or source_manager.durable()):
        raise ValueError('El archivo del maestro no está disponible.')
    import hashlib
    from catastro.master_d1 import Gateway
    from catastro.storage import R2
    rows = Gateway().read(
        'SELECT id,kind,object_key,sha256,observed_at,source_version FROM media WHERE id=?',
        [media_id])
    if not rows:
        raise ValueError('Archivo no disponible.')
    item = rows[0]
    key = item['object_key']
    if not key.startswith('geollaqta/') or '..' in key.split('/'):
        raise ValueError('Ruta de archivo no válida.')
    body, _ = R2(timeout=15).get(key, max_bytes=64_000_000)
    if item.get('sha256') and hashlib.sha256(body).hexdigest() != item['sha256']:
        raise ValueError('El archivo no coincide con su huella registrada.')
    mime = ('application/pdf' if body.startswith(b'%PDF-') else
            'image/jpeg' if body.startswith(b'\xff\xd8\xff') else
            'image/png' if body.startswith(b'\x89PNG\r\n\x1a\n') else None)
    if not mime:
        raise ValueError('Formato de archivo no disponible.')
    return body, mime


def _document_body(value, media, lot_id):
    if media and media.get('id'):
        return _master_medium_body(media['id'])
    if media and media.get('filename'):
        return master_dossier.archive_asset(lot_id, media['filename'])
    raise ValueError('El documento no está disponible en el Catastro Maestro.')


@require_GET
@required('cadastral_info')
def revisions(request):
    from catastro import master_layers
    try:
        response = JsonResponse({'sources': master_layers.revisions()})
        response['Cache-Control'] = 'private, no-store'
        return response
    except StorageError:
        return JsonResponse({'error': 'No se pudo consultar la versión compartida del plano.'}, status=503)


@require_GET
@required('cadastral_info')
def reference_geometry(request, source_id):
    from catastro import master_layers
    try:
        value = master_layers.radius(source_id, request.GET.get('lat', ''),
            request.GET.get('lng', ''), request.GET.get('radius', ''))
        if source_id.startswith('borrador-'):
            value = {**value, **{key:master_layers.public_draft_layer(value[key]) for key in ('lots','blocks')}}
        response = JsonResponse(value,
            json_dumps_params={'separators': (',', ':')})
        response['Cache-Control'] = 'no-store'
        return response
    except StorageError:
        return JsonResponse({'error': 'No se pudo leer el ajuste compartido. Vuelve a consultar.'}, status=503)
    except (ValueError, TypeError, OSError):
        return JsonResponse({'error': 'Fuente, ubicación o radio no válido.'}, status=400)


@require_GET
@required('cadastral_info')
def lot(request, lot_id):
    try:
        record_id = request.GET.get('record_id') or None
        dossier = master_dossier.load(lot_id, record_id, surface='acm')
        value = master_dossier.summary(dossier, record_id)
        response = JsonResponse(value, json_dumps_params={'ensure_ascii': False})
        response['Cache-Control'] = 'private, no-store'
        response['Vary'] = 'Cookie'
        if dossier.get('master_revision') is not None:
            response['X-Catastro-Master-Revision'] = str(
                dossier['master_revision'])
        return response
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    except StorageError as error:
        return JsonResponse({'error': str(error)}, status=503)


@require_GET
@required('cadastral_info')
def facade(request, lot_id):
    try:
        from PIL import Image
        value = master_dossier.load(lot_id, surface='acm')
        media = next((item for item in value.get('gallery') or [] if item.get('url')), None)
        if not media:
            raise ValueError('Fachada no disponible.')
        body, _ = _document_body(value, media, lot_id)
        if len(body) > 8_000_000:
            raise ValueError('Image too large')
        with Image.open(io.BytesIO(body)) as image:
            image.thumbnail((1200, 900))
            output = io.BytesIO()
            image.convert('RGB').save(output, format='JPEG', quality=85)
        response = HttpResponse(output.getvalue(), content_type='image/jpeg')
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except (OSError, ValueError, RuntimeError):
        raise Http404


@require_GET
@required('cadastral_pdf')
@required('cadastral_info')
def report_pdf(request, lot_id):
    try:
        record_id = request.GET.get('record_id') or None
        value = master_dossier.load(lot_id, record_id, surface='acm')
        summary = master_dossier.summary(value, record_id)
        selected = summary.get('selected_record_id')
        media = next((item for item in value.get('media') or []
                      if str(item.get('kind') or '').lower().endswith('pdf') and
                      str(item.get('record_id') or item.get('source_record_id') or '') ==
                      str(selected or '')), None)
        if media is None:
            media = next((item for item in value.get('media') or []
                          if str(item.get('kind') or '').lower().endswith('pdf')), None)
        body, _ = _document_body(value, media, lot_id)
        response = HttpResponse(body, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="reporte-catastral-{lot_id}.pdf"'
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except ValueError:
        return JsonResponse({'error': 'Lote o reporte catastral no válido.'}, status=400)
    except (OSError, RuntimeError, StorageError):
        return JsonResponse({'error': 'El PDF catastral no está disponible. Vuelve a intentarlo.'}, status=502)


@require_GET
@required('cadastral_info')
def archive_asset(request, lot_id, filename):
    permissions = getattr(getattr(request, 'acm_access', None), 'permissions', {})
    if filename.lower().endswith('.pdf') and not permissions.get('cadastral_pdf'):
        return JsonResponse({'error': 'La descarga de fichas no está habilitada.'},
                            status=403)
    try:
        body, content_type = master_dossier.archive_asset(lot_id, filename)
        response = HttpResponse(body, content_type=content_type)
        response['Content-Disposition'] = 'inline'
        response['Cache-Control'] = 'private, max-age=86400'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except StorageError:
        return JsonResponse({'error': 'El archivo del Catastro Maestro no está disponible.'}, status=503)
    except ValueError:
        raise Http404
