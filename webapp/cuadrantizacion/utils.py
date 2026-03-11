"""
Utilidades para el sistema de cuadrantización inmobiliaria.
"""
import json
from decimal import Decimal
from typing import List, Dict, Any
from django.db import transaction

from .models import ZonaValor, PropiedadValoracion
from ingestas.models import PropiedadRaw


def crear_zona_desde_geojson(geojson_data: Dict[str, Any], nombre: str, descripcion: str = "") -> ZonaValor:
    """
    Crea una ZonaValor a partir de datos GeoJSON.
    
    Args:
        geojson_data: Diccionario con datos GeoJSON
        nombre: Nombre de la zona
        descripcion: Descripción opcional
    
    Returns:
        ZonaValor creada
    """
    # Extraer coordenadas del GeoJSON
    if geojson_data.get('type') == 'FeatureCollection':
        features = geojson_data.get('features', [])
        if features:
            geometry = features[0].get('geometry', {})
        else:
            raise ValueError("GeoJSON no contiene features")
    elif geojson_data.get('type') == 'Feature':
        geometry = geojson_data.get('geometry', {})
    elif geojson_data.get('type') == 'Polygon':
        geometry = {'type': 'Polygon', 'coordinates': geojson_data.get('coordinates')}
    else:
        raise ValueError("Formato GeoJSON no soportado")
    
    # Convertir coordenadas GeoJSON a formato interno
    if geometry.get('type') == 'Polygon':
        # GeoJSON Polygon tiene anidación extra: [[[lat,lng], ...]]
        coordinates_geojson = geometry['coordinates'][0]  # Primer anillo exterior
        coordenadas = [[coord[1], coord[0]] for coord in coordinates_geojson]  # GeoJSON es [lng, lat]
    else:
        raise ValueError("Solo se soportan polígonos GeoJSON")
    
    # Crear zona
    zona = ZonaValor.objects.create(
        nombre_zona=nombre,
        descripcion=descripcion,
        coordenadas=coordenadas
    )
    
    return zona


def exportar_zona_a_geojson(zona: ZonaValor) -> Dict[str, Any]:
    """
    Exporta una ZonaValor a formato GeoJSON.
    
    Args:
        zona: ZonaValor a exportar
    
    Returns:
        Diccionario en formato GeoJSON
    """
    # Convertir coordenadas internas a GeoJSON [lng, lat]
    coordinates_geojson = [[coord[1], coord[0]] for coord in zona.coordenadas]
    
    # Asegurar polígono cerrado
    if coordinates_geojson[0] != coordinates_geojson[-1]:
        coordinates_geojson.append(coordinates_geojson[0])
    
    geojson = {
        "type": "Feature",
        "properties": {
            "id": zona.id,
            "nombre": zona.nombre_zona,
            "descripcion": zona.descripcion,
            "precio_promedio_m2": float(zona.precio_promedio_m2) if zona.precio_promedio_m2 else None,
            "area_total": float(zona.area_total) if zona.area_total else None,
            "cantidad_propiedades": zona.cantidad_propiedades_analizadas,
            "color_fill": zona.color_fill,
            "color_borde": zona.color_borde,
            "opacidad": zona.opacidad
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [coordinates_geojson]
        }
    }
    
    return geojson


def calcular_valoracion_propiedad(propiedad: PropiedadRaw, zona: ZonaValor = None) -> PropiedadValoracion:
    """
    Calcula la valoración (precio por m²) de una propiedad.
    
    Args:
        propiedad: PropiedadRaw a valorar
        zona: ZonaValor opcional (si no se proporciona, se intenta encontrar)
    
    Returns:
        PropiedadValoracion creada o actualizada
    """
    # Intentar encontrar zona si no se proporciona
    if not zona and propiedad.coordenadas:
        try:
            # Parsear coordenadas de string "lat,lng"
            coords_str = propiedad.coordenadas.strip()
            if ',' in coords_str:
                lat_str, lng_str = coords_str.split(',', 1)
                lat = float(lat_str.strip())
                lng = float(lng_str.strip())
                
                from .services import encontrar_zona_por_punto
                zona = encontrar_zona_por_punto(lat, lng)
        except (ValueError, AttributeError):
            pass
    
    # Calcular precio por m² si hay datos
    precio_m2 = None
    precio_venta = propiedad.precio_usd
    metros_cuadrados = propiedad.area_construida or propiedad.area_terreno
    
    if precio_venta and metros_cuadrados and metros_cuadrados > 0:
        precio_m2 = precio_venta / metros_cuadrados
    
    # Determinar si es comparable
    es_comparable = bool(
        precio_m2 and 
        precio_venta and 
        metros_cuadrados and
        propiedad.tipo_propiedad in ['casa', 'departamento', 'terreno', 'local', 'oficina']
    )
    
    # Crear o actualizar valoración
    valoracion, created = PropiedadValoracion.objects.update_or_create(
        propiedad=propiedad,
        zona=zona,
        defaults={
            'precio_m2': precio_m2,
            'precio_venta': precio_venta,
            'metros_cuadrados': metros_cuadrados,
            'es_comparable': es_comparable,
            'metodo_calculo': 'directo' if precio_m2 else 'estimado'
        }
    )
    
    return valoracion


@transaction.atomic
def migrar_propiedades_existentes(batch_size: int = 100) -> Dict[str, int]:
    """
    Migra propiedades existentes a valoraciones.
    
    Args:
        batch_size: Tamaño del lote para procesamiento
    
    Returns:
        Estadísticas de migración
    """
    propiedades = PropiedadRaw.objects.all()
    total = propiedades.count()
    procesadas = 0
    valoraciones_creadas = 0
    valoraciones_actualizadas = 0
    
    for i in range(0, total, batch_size):
        batch = propiedades[i:i + batch_size]
        
        for propiedad in batch:
            valoracion = calcular_valoracion_propiedad(propiedad)
            
            if valoracion.pk:
                valoraciones_actualizadas += 1
            else:
                valoraciones_creadas += 1
            
            procesadas += 1
    
    return {
        'total_propiedades': total,
        'procesadas': procesadas,
        'valoraciones_creadas': valoraciones_creadas,
        'valoraciones_actualizadas': valoraciones_actualizadas
    }


def generar_heatmap_data(zonas=None):
    """
    Genera datos para visualización heatmap de precios por m².
    
    Args:
        zonas: QuerySet de ZonaValor (opcional)
    
    Returns:
        Lista de puntos para heatmap
    """
    if zonas is None:
        zonas = ZonaValor.objects.filter(activo=True, precio_promedio_m2__isnull=False)
    
    heatmap_data = []
    
    for zona in zonas:
        if not zona.coordenadas or len(zona.coordenadas) < 3:
            continue
        
        # Calcular centroide del polígono
        lats = [p[0] for p in zona.coordenadas]
        lngs = [p[1] for p in zona.coordenadas]
        
        centro_lat = sum(lats) / len(lats)
        centro_lng = sum(lngs) / len(lngs)
        
        # Determinar peso basado en precio
        precio = float(zona.precio_promedio_m2) if zona.precio_promedio_m2 else 1000
        peso = min(1.0, precio / 5000)  # Normalizar a 0-1
        
        heatmap_data.append({
            'lat': centro_lat,
            'lng': centro_lng,
            'weight': peso,
            'zona_id': zona.id,
            'precio_m2': precio,
            'nombre': zona.nombre_zona
        })
    
    return heatmap_data


def obtener_rango_colores(precio_m2: Decimal) -> str:
    """
    Determina el color basado en el precio por m².
    
    Args:
        precio_m2: Precio por metro cuadrado
    
    Returns:
        Color HEX
    """
    if not precio_m2:
        return '#9E9E9E'  # Gris
    
    precio = float(precio_m2)
    
    # Escala de colores: verde (bajo) -> amarillo -> rojo (alto)
    if precio < 1000:
        return '#4CAF50'  # Verde
    elif precio < 2000:
        return '#FFC107'  # Amarillo
    elif precio < 3000:
        return '#FF9800'  # Naranja
    else:
        return '#F44336'  # Rojo


def calcular_estadisticas_globales() -> Dict[str, Any]:
    """
    Calcula estadísticas globales del sistema.
    
    Returns:
        Diccionario con estadísticas
    """
    zonas = ZonaValor.objects.filter(activo=True)
    valoraciones = PropiedadValoracion.objects.filter(es_comparable=True)
    
    # Estadísticas de zonas
    zonas_con_precio = zonas.exclude(precio_promedio_m2__isnull=True)
    
    if zonas_con_precio.exists():
        precio_promedio_global = zonas_con_precio.aggregate(
            avg=Avg('precio_promedio_m2')
        )['avg']
        zonas_mas_cara = zonas_con_precio.order_by('-precio_promedio_m2').first()
        zonas_mas_barata = zonas_con_precio.order_by('precio_promedio_m2').first()
    else:
        precio_promedio_global = None
        zonas_mas_cara = None
        zonas_mas_barata = None
    
    # Estadísticas de valoraciones
    if valoraciones.exists():
        valoraciones_stats = valoraciones.aggregate(
            total=Count('id'),
            avg_precio_m2=Avg('precio_m2'),
            min_precio_m2=Min('precio_m2'),
            max_precio_m2=Max('precio_m2')
        )
    else:
        valoraciones_stats = {'total': 0, 'avg_precio_m2': None}
    
    return {
        'total_zonas': zonas.count(),
        'zonas_con_precio': zonas_con_precio.count(),
        'precio_promedio_global': precio_promedio_global,
        'zona_mas_cara': {
            'id': zonas_mas_cara.id if zonas_mas_cara else None,
            'nombre': zonas_mas_cara.nombre_zona if zonas_mas_cara else None,
            'precio_m2': zonas_mas_cara.precio_promedio_m2 if zonas_mas_cara else None
        },
        'zona_mas_barata': {
            'id': zonas_mas_barata.id if zonas_mas_barata else None,
            'nombre': zonas_mas_barata.nombre_zona if zonas_mas_barata else None,
            'precio_m2': zonas_mas_barata.precio_promedio_m2 if zonas_mas_barata else None
        },
        'valoraciones': valoraciones_stats,
        'fecha_actualizacion': timezone.now()
    }


# Import para funciones de agregación
from django.db.models import Avg, Min, Max, Count
from django.utils import timezone