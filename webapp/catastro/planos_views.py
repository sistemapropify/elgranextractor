"""Map workspace for reviewing georeferenced plans without altering the archive."""
import json
import hashlib
from pathlib import Path
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from map_config import google_maps_api_key

from .views import admin_required
from . import cad_reader, plan_adjustments, source_manager
from .storage import R2, StorageError


@require_GET
@admin_required
@ensure_csrf_cookie
def viewer(request):
    initial = None
    job_id = request.GET.get('plano')
    if job_id:
        try:
            value = cad_reader.status(job_id)
            if value['status'] == 'completed':
                initial = value
        except (ValueError, OSError):
            pass
    response = render(request, 'catastro/visor_planos.html', {
        'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', None)
                               if getattr(settings, 'GOOGLE_MAPS_API_KEY', None) is not None
                               else google_maps_api_key(),
        'cad_available': cad_reader.available(),
        'cad_crs': cad_reader.CRS,
        'cad_initial_state': initial,
    })
    response['Cache-Control'] = 'private, no-store'
    return response


@require_POST
@csrf_protect
@admin_required
def upload(request):
    try:
        job_id = cad_reader.start_import(request.FILES.get('file'), {
            'name': request.POST.get('name'), 'sheet_code': request.POST.get('sheet_code'),
            'ubigeo': request.POST.get('ubigeo')})
        return JsonResponse({'id': job_id}, status=202)
    except (ValueError, RuntimeError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    except OSError:
        return JsonResponse({'error': 'No se pudo guardar el DWG o iniciar su lectura. Revisa el almacenamiento del servidor.'}, status=503)


@require_GET
@admin_required
def inventory(request):
    response = JsonResponse({'dwg': cad_reader.inventory()})
    response['Cache-Control'] = 'private, no-store'
    return response


@require_GET
@admin_required
def geollaqta_inventory(request):
    ubigeo = request.GET.get('ubigeo', '040126').strip()
    if len(ubigeo) != 6 or not ubigeo.isdigit():
        return JsonResponse({'error': 'UBIGEO no válido.'}, status=400)
    catalog_file = Path(__file__).resolve().parents[1] / 'cuadrantizacion' / 'geollaqta_districts.json'
    catalog = json.loads(catalog_file.read_text(encoding='utf8'))
    district = next((item for item in catalog.get('districts', [])
                     if item.get('ubigeo') == ubigeo), None)
    response = JsonResponse({
        'ubigeo': ubigeo,
        'district': district.get('name') if district else None,
        'expected_lots': district.get('published_lots') if district else None,
        'catalog_checked_at': catalog.get('checked_at'),
        'archive_prefix': 'geollaqta/' + ubigeo + '/',
        'map_url': ('/cuadrantizacion/mapa/?catastro=' + district['slug'])
                   if district and district.get('slug') else '/cuadrantizacion/mapa/',
        'catalog_url': '/catastro/maestro/fuentes/#sources-catalog-query',
    })
    response['Cache-Control'] = 'private, no-store'
    return response


@require_GET
@admin_required
def source_thumbnail(request, version_id):
    payload = source_manager.version_payload(version_id)
    if not payload:
        return JsonResponse({'error': 'Versión de datos no disponible.'}, status=404)
    media = payload.get('media') or []
    image = next((item for item in media
                  if isinstance(item, dict)
                  and item.get('kind') in ('facade_image', 'interior_image', 'photo', 'image')
                  and isinstance(item.get('object_key'), str)), None)
    if not image:
        return JsonResponse({'error': 'El lote no tiene fotografía archivada.'}, status=404)
    key = image['object_key']
    if not key.startswith('geollaqta/') or '..' in key.split('/'):
        return JsonResponse({'error': 'Ruta de fotografía no válida.'}, status=404)
    try:
        body, _ = R2().get(key)
    except StorageError as error:
        return JsonResponse({'error': str(error)}, status=503)
    if image.get('sha256') and hashlib.sha256(body).hexdigest() != image['sha256']:
        return JsonResponse({'error': 'La fotografía no coincide con su huella.'}, status=409)
    mime = ('image/jpeg' if body.startswith(b'\xff\xd8\xff') else
            'image/png' if body.startswith(b'\x89PNG\r\n\x1a\n') else None)
    if not mime:
        return JsonResponse({'error': 'Formato de fotografía no disponible.'}, status=415)
    response = HttpResponse(body, content_type=mime)
    response['Cache-Control'] = 'private, max-age=300'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@require_GET
@admin_required
def import_status(request, job_id):
    try:
        response = JsonResponse(cad_reader.status(job_id))
        response['Cache-Control'] = 'private, no-store'
        return response
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=404)


@require_GET
@admin_required
def layer_features(request, job_id):
    try:
        value = cad_reader.features(job_id, request.GET.get('layer', ''),
                                    int(request.GET.get('offset', 0)), request.GET.get('crs', 'unknown'))
        response = JsonResponse(value)
        response['Cache-Control'] = 'private, no-store'
        return response
    except (ValueError, TypeError):
        return JsonResponse({'error': 'No se pudo mostrar la capa con estos parámetros. Revisa el sistema de coordenadas.'}, status=400)
    except Exception:
        return JsonResponse({'error': 'No se pudo transformar la capa. Revisa el sistema de coordenadas seleccionado.'}, status=422)


@csrf_protect
@admin_required
def adjustments(request, job_id):
    if request.method not in ('GET', 'POST'):
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    try:
        crs = request.GET.get('crs', 'unknown')
        if request.method == 'POST':
            if len(request.body) > 8 * 1024 * 1024:
                raise ValueError('Los ajustes superan el tamaño admitido.')
            payload = json.loads(request.body)
            if not isinstance(payload, dict):
                raise ValueError('Formato de ajustes no válido.')
            user = getattr(request, 'current_user', None) or request.user
            value = plan_adjustments.save(job_id, crs, payload, getattr(user, 'username', '') or getattr(user, 'pk', 'administrador'))
        else:
            value = plan_adjustments.read(job_id, crs)
        response = JsonResponse(value)
        response['Cache-Control'] = 'private, no-store'
        return response
    except plan_adjustments.Conflict as error:
        return JsonResponse({'error': str(error)}, status=409)
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        return JsonResponse({'error': str(error) or 'Ajustes no válidos.'}, status=400)
    except OSError:
        return JsonResponse({'error': 'No se pudieron guardar o leer los ajustes. Tus cambios siguen en pantalla; vuelve a intentar.'}, status=503)
