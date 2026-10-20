"""Authenticated master geometry preview. Never changes production archives."""
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_protect
from map_config import google_maps_api_key
from .views import admin_required
from . import master_layers
from . import source_placement
from .storage import StorageError
import json


@require_GET
@admin_required
def viewer(request):
    response = render(request, 'catastro/maestro.html', {
        'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', None)
                              if getattr(settings, 'GOOGLE_MAPS_API_KEY', None) is not None
                              else google_maps_api_key(),
    })
    response['Cache-Control'] = 'private, no-store'
    return response


@require_GET
@admin_required
def catalogue(request):
    try:
        response = JsonResponse(master_layers.catalogue())
    except StorageError:
        return JsonResponse({'error': 'No se pudo consultar la posición compartida del plano. Vuelve a consultar.'}, status=503)
    response['Cache-Control'] = 'private, no-cache'
    return response


@require_GET
@admin_required
def layer(request, source_id, layer_key):
    try:
        value = master_layers.layer(source_id, layer_key, request.GET.get('ubigeo', ''),
                                    master_layers.bbox(request.GET.get('bbox')))
        response = JsonResponse(value, json_dumps_params={'separators': (',', ':')})
        response['Cache-Control'] = 'private, no-cache'
        return response
    except StorageError:
        return JsonResponse({'error': 'No se pudo consultar la posición compartida del plano. Vuelve a consultar.'}, status=503)
    except (ValueError, OSError) as error:
        return JsonResponse({'error': str(error) if isinstance(error, ValueError)
                             else 'La capa todavía no está disponible.'}, status=400)


@csrf_protect
@admin_required
def placement(request, source_id):
    if source_id not in master_layers.SOURCES:
        return JsonResponse({'error': 'Fuente no disponible.'}, status=404)
    folder = master_layers.SOURCES[source_id]
    try:
        if request.method == 'GET':
            value = source_placement.read(folder)
        elif request.method == 'POST':
            if len(request.body) > 1024*1024:
                raise ValueError('Ajuste demasiado grande.')
            user = getattr(request, 'current_user', None) or request.user
            value = source_placement.save(folder, json.loads(request.body),
                                          getattr(user, 'username', '') or getattr(user, 'pk', 'administrador'))
        else:
            return JsonResponse({'error': 'Método no permitido.'}, status=405)
        response = JsonResponse(value)
        response['Cache-Control'] = 'private, no-store'
        return response
    except source_placement.Conflict as error:
        return JsonResponse({'error': str(error)}, status=409)
    except (ValueError, TypeError) as error:
        return JsonResponse({'error': str(error)}, status=400)
    except (OSError, StorageError):
        return JsonResponse({'error': 'No se pudo guardar la posición. El ajuste sigue en pantalla; vuelve a intentar.'}, status=503)
