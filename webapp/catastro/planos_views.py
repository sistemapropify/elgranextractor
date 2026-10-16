"""Map workspace for reviewing georeferenced plans without altering the archive."""
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from map_config import google_maps_api_key

from .views import admin_required
from . import cad_reader


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
        job_id = cad_reader.start_import(request.FILES.get('file'))
        return JsonResponse({'id': job_id}, status=202)
    except (ValueError, RuntimeError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    except OSError:
        return JsonResponse({'error': 'No se pudo guardar el DWG o iniciar su lectura. Revisa el almacenamiento del servidor.'}, status=503)


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
