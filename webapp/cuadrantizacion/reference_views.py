"""Reference geometry uses Cuadrantización's existing read permission."""
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .geollaqta import _authenticated
from catastro import master_layers
from catastro.storage import StorageError


@require_GET
def layer(request, source_id, layer_key):
    if not _authenticated(request):
        return JsonResponse({'error': 'Inicia sesión para consultar el catastro.'}, status=401)
    try:
        response = JsonResponse(master_layers.layer(source_id, layer_key, request.GET.get('ubigeo', ''),
                                                    original=request.GET.get('original') == '1'),
                                json_dumps_params={'separators': (',', ':')})
        response['Cache-Control'] = 'private, no-store'
        return response
    except StorageError:
        return JsonResponse({'error': 'No se pudo consultar el ajuste compartido. Vuelve a consultar.'}, status=503)
    except (ValueError, OSError):
        return JsonResponse({'error': 'Fuente o capa no disponible para este distrito.'}, status=400)
