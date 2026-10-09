"""Configuración compartida del plano y las zonas para Cuadrantización y ACM."""
from django.http import JsonResponse
from django.templatetags.static import static
from django.views.decorators.http import require_GET


def serialize_layer(layer, url_field):
    data = layer.a_diccionario()
    url = (data.get(url_field) or '').strip()
    if url and not url.startswith(('http://', 'https://', '/')):
        data[url_field] = static(url)
    return data


def map_layers_config(include_zones=True):
    from .models import CapaRasterMapa, CapaVectorialMapa, ZonaValor
    return {
        'raster': [serialize_layer(layer, 'imagen_url') for layer in
                   CapaRasterMapa.objects.filter(activo=True)
                   .exclude(imagen_url__icontains='zonificacion_pdm_2016_2025.png').order_by('orden', 'id')],
        'vectoriales': [serialize_layer(layer, 'geojson_url') for layer in
                        CapaVectorialMapa.objects.filter(activo=True).order_by('orden', 'id')],
        'zonas': list(ZonaValor.objects.filter(activo=True).order_by('id').values(
            'id', 'nombre_zona', 'nivel', 'coordenadas', 'color_fill', 'color_borde', 'opacidad'
        )) if include_zones else [],
    }


@require_GET
def map_layers_api(request):
    users = (getattr(request, 'current_user', None), getattr(request, 'user', None))
    if not any(user and getattr(user, 'is_active', False) and
               getattr(user, 'is_authenticated', False) for user in users):
        return JsonResponse({'error': 'Inicia sesión para actualizar las capas.'}, status=401)
    response = JsonResponse(map_layers_config())
    response['Cache-Control'] = 'no-store'
    return response
