"""Authenticated master geometry preview. Never changes production archives."""
from django.conf import settings
from django.http import JsonResponse
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect
from map_config import google_maps_api_key
from .views import admin_required
from . import master_layers
from . import master_model
from . import raster_overlays
from . import source_manager
from . import source_manager_views
from . import source_placement
from . import vector_snapshots
from . import manual_parks
from .storage import StorageError
import json


@require_GET
@admin_required
def viewer(request):
    response = render(request, 'catastro/maestro.html', {
        'data_model': master_model.value(),
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


@require_GET
@admin_required
def vector_snapshot(request, ubigeo, layer):
    try:
        value = vector_snapshots.read_snapshot(ubigeo, layer)
        response = JsonResponse(value, json_dumps_params={'separators': (',', ':')})
        response['Cache-Control'] = 'private, no-store'
        return response
    except StorageError as error:
        return JsonResponse({'error': str(error)}, status=503)
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=404)


@csrf_protect
@admin_required
def park_lots(request):
    try:
        if request.method == 'GET':
            value = manual_parks.read(request.GET.get('ubigeo', ''))
        elif request.method == 'POST':
            if len(request.body) > 8 * 1024 * 1024:
                raise ValueError('La clasificación enviada es demasiado grande.')
            payload = json.loads(request.body)
            actor = getattr(request, 'current_user', None) or request.user
            value = manual_parks.save(
                payload.get('ubigeo'), payload.get('lots'),
                payload.get('token'), getattr(actor, 'username', '') or
                str(getattr(actor, 'pk', 'administrador')))
        else:
            return JsonResponse({'error': 'Método no permitido.'}, status=405)
        response = JsonResponse(value)
        response['Cache-Control'] = 'private, no-store'
        return response
    except manual_parks.Conflict as error:
        return JsonResponse({'error': str(error)}, status=409)
    except StorageError as error:
        return JsonResponse({'error': str(error)}, status=503)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return JsonResponse({'error': str(error)}, status=400)


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


def _raster_store():
    if not (source_manager.enabled() or source_manager.durable()):
        raise PermissionError('El mosaico satelital no está habilitado en este entorno.')
    return source_manager.store()


def _raster_read_store():
    if not (source_manager.enabled() or source_manager.durable()):
        raise PermissionError('El mosaico satelital no está habilitado en este entorno.')
    return source_manager.map_store()


def _raster_actor(request):
    user = getattr(request, 'current_user', None) or request.user
    return getattr(user, 'username', '') or str(getattr(user, 'pk', 'administrador'))


def authenticated_map_user(view):
    def wrapped(request, *args, **kwargs):
        user = getattr(request, 'current_user', None) or getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', False):
            return JsonResponse({'error': 'Inicia sesión para consultar el mapa catastral.'}, status=401)
        return view(request, *args, **kwargs)
    return wrapped


@require_GET
@authenticated_map_user
def raster_catalog(request):
    """Single Catastro Maestro feed consumed by every map view."""
    try:
        store = _raster_read_store()
        ubigeo = request.GET.get('ubigeo', '')
        overlays = (raster_overlays.list_overlays(store, ubigeo) if ubigeo
                    else raster_overlays.list_all_overlays(store))
        response = JsonResponse({'overlays': overlays, 'revision': store.revision},
                                json_dumps_params={'ensure_ascii': False})
        response['Cache-Control'] = 'private, no-store'
        return response
    except PermissionError as error:
        return JsonResponse({'error': str(error)}, status=404)
    except StorageError as error:
        return JsonResponse({'error': str(error)}, status=503)
    except (ValueError, TypeError, KeyError) as error:
        return JsonResponse({'error': str(error) if isinstance(error, ValueError)
                             else 'El catálogo satelital no está disponible.'}, status=400)


@csrf_protect
@admin_required
def raster_layers(request):
    try:
        if request.method == 'GET':
            store = _raster_read_store()
            ubigeo = request.GET.get('ubigeo', '')
            value = {'overlays': raster_overlays.list_overlays(store, ubigeo),
                     'revision': store.revision}
        elif request.method == 'POST':
            store = _raster_store()
            request.upload_handlers = [source_manager_views.MemoryPDFUpload(request)]
            upload = request.FILES.get('image')
            if upload is None:
                raise ValueError('Selecciona una fotografía JPEG o PNG.')
            value = raster_overlays.register_image(
                store, upload.read(), upload.name, request.POST.get('name', ''),
                request.POST.get('ubigeo', ''), _raster_actor(request))
            value = {'overlay': value, 'revision': store.revision}
        else:
            return JsonResponse({'error': 'Método no permitido.'}, status=405)
        response = JsonResponse(value, json_dumps_params={'ensure_ascii': False})
        response['Cache-Control'] = 'private, no-store'
        return response
    except PermissionError as error:
        return JsonResponse({'error': str(error)}, status=404)
    except source_manager_views.Conflict as error:
        return JsonResponse({'error': str(error)}, status=409)
    except StorageError as error:
        return JsonResponse({'error': str(error)}, status=503)
    except (ValueError, TypeError, KeyError) as error:
        return JsonResponse({'error': str(error) if isinstance(error, ValueError)
                             else 'Revisa los datos de la capa satelital.'}, status=400)


@csrf_protect
@admin_required
@require_POST
def raster_calibration(request, overlay_id):
    try:
        store = _raster_store()
        if len(request.body) > 128 * 1024:
            raise ValueError('La calibración enviada es demasiado grande.')
        value = json.loads(request.body)
        if not isinstance(value, dict):
            raise ValueError('La calibración no es válida.')
        overlay = raster_overlays.calibrate(
            store, overlay_id, value.get('state'), value.get('ubigeo', ''),
            _raster_actor(request))
        response = JsonResponse({'overlay': overlay, 'revision': store.revision})
        response['Cache-Control'] = 'private, no-store'
        return response
    except PermissionError as error:
        return JsonResponse({'error': str(error)}, status=404)
    except source_manager_views.Conflict as error:
        return JsonResponse({'error': str(error)}, status=409)
    except StorageError as error:
        return JsonResponse({'error': str(error)}, status=503)
    except (ValueError, TypeError, KeyError) as error:
        return JsonResponse({'error': str(error) if isinstance(error, ValueError)
                             else 'Revisa la calibración.'}, status=400)


@require_GET
@authenticated_map_user
def raster_image(request, overlay_id):
    try:
        store = _raster_read_store()
        body, content_type = raster_overlays.image_body(
            store, overlay_id, request.GET.get('ubigeo', ''))
        response = HttpResponse(body, content_type=content_type)
        response['Cache-Control'] = 'private, max-age=3600'
        response['Content-Disposition'] = 'inline'
        return response
    except PermissionError as error:
        return JsonResponse({'error': str(error)}, status=404)
    except StorageError as error:
        return JsonResponse({'error': str(error)}, status=503)
    except (ValueError, TypeError, KeyError) as error:
        return JsonResponse({'error': str(error) if isinstance(error, ValueError)
                             else 'La imagen no está disponible.'}, status=404)
