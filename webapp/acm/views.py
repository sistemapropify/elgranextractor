import json
import math
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from ingestas.models import PropiedadRaw
from .utils import haversine, calcular_precio_m2


def acm_view(request):
    """
    Vista principal del módulo ACM.
    Renderiza el template con el formulario y el mapa.
    """
    # Obtener tipos de propiedad únicos para el select (de PropiedadRaw)
    tipos_locales = PropiedadRaw.objects.exclude(
        tipo_propiedad__isnull=True
    ).exclude(
        tipo_propiedad=''
    ).values_list('tipo_propiedad', flat=True).distinct()
    
    # Obtener tipos de propiedad de Propifai (si está disponible)
    tipos_propifai = set()
    try:
        from propifai.models import PropifaiProperty
        # Usar la base de datos 'propifai' explícitamente
        tipos_propifai = set(PropifaiProperty.objects.using('propifai').exclude(
            property_type__isnull=True
        ).exclude(
            property_type=''
        ).values_list('property_type', flat=True).distinct())
    except Exception as e:
        print(f"Error obteniendo tipos de Propifai: {e}")
    
    # Combinar tipos de ambas fuentes
    todos_tipos = sorted(set(list(tipos_locales) + list(tipos_propifai)))
    
    # Filtrar solo tipos comunes (pueden haber muchos)
    tipos_comunes = [tipo for tipo in todos_tipos if tipo in [
        'Terreno', 'Casa', 'Departamento', 'Oficina', 'Local Comercial', 'Bodega'
    ]]
    if not tipos_comunes:
        tipos_comunes = list(todos_tipos)[:10]  # Tomar primeros 10 si no hay coincidencias
    
    context = {
        'tipos_propiedad': tipos_comunes,
        'google_maps_api_key': 'AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q',  # Reutilizar la misma key del proyecto
    }
    return render(request, 'acm/acm_analisis.html', context)


@csrf_exempt
def buscar_comparables(request):
    """
    Endpoint AJAX que recibe parámetros de búsqueda y retorna propiedades comparables.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        lat = float(data.get('lat'))
        lng = float(data.get('lng'))
        radio = float(data.get('radio', 500))  # metros
        tipo_propiedad = data.get('tipo_propiedad', '').strip()
        
        # Validar coordenadas
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return JsonResponse({'status': 'error', 'message': 'Coordenadas inválidas'}, status=400)
        
        # Obtener propiedades locales (PropiedadRaw)
        propiedades_locales = PropiedadRaw.objects.exclude(
            coordenadas__isnull=True
        ).exclude(
            coordenadas=''
        )
        
        # Filtrar por tipo si se especifica
        if tipo_propiedad:
            propiedades_locales = propiedades_locales.filter(
                Q(tipo_propiedad__icontains=tipo_propiedad) |
                Q(atributos_extras__tipo_propiedad__icontains=tipo_propiedad) |
                Q(atributos_extras__tipo__icontains=tipo_propiedad)
            )
        
        # Convertir a lista para procesar
        propiedades_list = list(propiedades_locales)
        
        # Obtener propiedades de Propifai (si está disponible)
        propiedades_propifai_list = []
        try:
            from propifai.models import PropifaiProperty
            from propifai.mapeo_ubicaciones import DEPARTAMENTOS, PROVINCIAS, DISTRITOS
            
            # Obtener propiedades de Propifai con coordenadas
            propiedades_propifai = PropifaiProperty.objects.using('propifai').exclude(
                latitude__isnull=True
            ).exclude(
                longitude__isnull=True
            )
            
            # Filtrar por tipo si se especifica
            if tipo_propiedad:
                propiedades_propifai = propiedades_propifai.filter(
                    Q(property_type__icontains=tipo_propiedad) |
                    Q(title__icontains=tipo_propiedad)
                )
            
            propiedades_propifai_list = list(propiedades_propifai)
            print(f"DEBUG ACM: Obtenidas {len(propiedades_propifai_list)} propiedades de Propifai")
            
        except Exception as e:
            print(f"Error obteniendo propiedades de Propifai para ACM: {e}")
        
        # Combinar ambas listas
        todas_propiedades = propiedades_list + propiedades_propifai_list
        
        # Filtrar por distancia usando Haversine
        propiedades_cercanas = []
        for prop in todas_propiedades:
            # Determinar coordenadas según el tipo de propiedad
            if hasattr(prop, 'lat') and hasattr(prop, 'lng'):
                # Propiedad local (PropiedadRaw)
                prop_lat = prop.lat
                prop_lng = prop.lng
                if prop_lat is None or prop_lng is None:
                    continue
                    
                # Calcular distancia
                distancia = haversine(lat, lng, prop_lat, prop_lng)
                if distancia > radio:
                    continue
                
                # Calcular precio por m² para propiedades locales
                precio_m2_info = calcular_precio_m2(prop)
                
                # Obtener ubicación
                distrito = prop.distrito or ''
                provincia = prop.provincia or ''
                departamento = prop.departamento or ''
                
                # Crear diccionario para propiedad local
                propiedad_dict = {
                    'id': prop.id,
                    'lat': prop_lat,
                    'lng': prop_lng,
                    'tipo': prop.tipo_propiedad or 'No especificado',
                    'precio': float(prop.precio_usd) if prop.precio_usd else None,
                    'precio_final': float(prop.precio_final_venta) if prop.precio_final_venta else None,
                    'metros_construccion': float(prop.area_construida) if prop.area_construida else None,
                    'metros_terreno': float(prop.area_terreno) if prop.area_terreno else None,
                    'habitaciones': prop.numero_habitaciones,
                    'baños': prop.numero_banos,
                    'estado': prop.get_estado_propiedad_display() if prop.estado_propiedad else 'En Publicación',
                    'distrito': distrito,
                    'provincia': provincia,
                    'departamento': departamento,
                    'imagen_url': prop.primera_imagen(),
                    'precio_m2': precio_m2_info.get('precio_m2'),
                    'precio_m2_final': precio_m2_info.get('precio_m2_final'),
                    'distancia_metros': round(distancia, 2),
                    'fuente': 'local',
                    'es_propify': False,
                }
                
            else:
                # Propiedad de Propifai
                prop_lat = prop.latitude
                prop_lng = prop.longitude
                if prop_lat is None or prop_lng is None:
                    continue
                    
                # Calcular distancia
                distancia = haversine(lat, lng, prop_lat, prop_lng)
                if distancia > radio:
                    continue
                
                # Obtener nombres mapeados de ubicación
                departamento_id = str(prop.department) if prop.department else ''
                provincia_id = str(prop.province) if prop.province else ''
                distrito_id = str(prop.district) if prop.district else ''
                
                departamento_nombre = DEPARTAMENTOS.get(departamento_id, departamento_id)
                provincia_nombre = PROVINCIAS.get(provincia_id, provincia_id)
                distrito_nombre = DISTRITOS.get(distrito_id, distrito_id)
                
                # Calcular precio por m² aproximado para Propifai
                precio_m2 = None
                precio_m2_final = None
                if prop.price and prop.built_area:
                    try:
                        precio_m2 = float(prop.price) / float(prop.built_area)
                    except (ValueError, ZeroDivisionError):
                        pass
                
                # Crear diccionario para propiedad Propifai
                propiedad_dict = {
                    'id': prop.id,
                    'lat': prop_lat,
                    'lng': prop_lng,
                    'tipo': prop.property_type or 'No especificado',
                    'precio': float(prop.price) if prop.price else None,
                    'precio_final': float(prop.price) if prop.price else None,  # Mismo precio
                    'metros_construccion': float(prop.built_area) if prop.built_area else None,
                    'metros_terreno': float(prop.land_area) if prop.land_area else None,
                    'habitaciones': prop.bedrooms,
                    'baños': prop.bathrooms,
                    'estado': 'En Publicación',  # Propifai no tiene estado
                    'distrito': distrito_nombre,
                    'provincia': provincia_nombre,
                    'departamento': departamento_nombre,
                    'imagen_url': None,  # Propifai no tiene imágenes en este modelo básico
                    'precio_m2': precio_m2,
                    'precio_m2_final': precio_m2_final,
                    'distancia_metros': round(distancia, 2),
                    'fuente': 'propifai',
                    'es_propify': True,
                    'codigo': prop.code,
                    'titulo': prop.title,
                }
            
            propiedades_cercanas.append(propiedad_dict)
        
        # Ordenar por distancia (más cercano primero)
        propiedades_cercanas.sort(key=lambda x: x['distancia_metros'])
        
        return JsonResponse({
            'status': 'ok',
            'total': len(propiedades_cercanas),
            'propiedades': propiedades_cercanas,
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido'}, status=400)
    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': f'Error en los datos: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error interno: {str(e)}'}, status=500)