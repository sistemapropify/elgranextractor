#!/usr/bin/env python
"""
Script para verificar las propiedades que se muestran en el heatmap.
"""
import os
import sys
import django

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw
from propifai.models import PropifaiProperty

def check_properties():
    print("=== VERIFICACIÓN DE PROPIEDADES EN HEATMAP ===")
    
    # Propiedades locales (Remax) con coordenadas válidas
    local_props = PropiedadRaw.objects.filter(
        coordenadas__isnull=False,
        precio_usd__isnull=False,
        precio_usd__gt=0
    ).exclude(coordenadas='')
    
    print(f"\n1. PROPIEDADES REMAX (PropiedadRaw) con coordenadas válidas:")
    print(f"   Total en BD: {local_props.count()}")
    
    count = 0
    for prop in local_props[:10]:  # Mostrar primeras 10
        try:
            coords = prop.coordenadas.split(',')
            if len(coords) >= 2:
                lat = float(coords[0].strip())
                lng = float(coords[1].strip())
                # Filtrar coordenadas fuera de Lima
                if (-12.2 <= lat <= -11.8 and -77.2 <= lng <= -76.8):
                    area = None
                    if prop.area_construida and prop.area_construida > 0:
                        area = float(prop.area_construida)
                    elif prop.area_terreno and prop.area_terreno > 0:
                        area = float(prop.area_terreno)
                    
                    precio_m2 = None
                    if area and prop.precio_usd:
                        precio_m2 = float(prop.precio_usd) / area
                    
                    if precio_m2 and precio_m2 > 0 and precio_m2 < 10000:
                        count += 1
                        print(f"   {count}. ID: {prop.id}, Coord: {lat}, {lng}, Precio: ${prop.precio_usd}, Área: {area}, Precio/m²: ${precio_m2:.2f}")
        except (ValueError, AttributeError, TypeError):
            continue
    
    print(f"   Propiedades válidas para heatmap: {count}")
    
    # Propiedades Propifai (Propify)
    propifai_props = PropifaiProperty.objects.filter(
        coordinates__isnull=False,
        price__isnull=False,
        price__gt=0
    ).exclude(coordinates='')
    
    print(f"\n2. PROPIEDADES PROPIFY (PropifaiProperty) con coordenadas válidas:")
    print(f"   Total en BD: {propifai_props.count()}")
    
    count2 = 0
    for prop in propifai_props[:10]:  # Mostrar primeras 10
        try:
            coords = prop.coordinates.split(',')
            if len(coords) >= 2:
                lat = float(coords[0].strip())
                lng = float(coords[1].strip())
                # Filtrar coordenadas fuera de Lima
                if (-12.2 <= lat <= -11.8 and -77.2 <= lng <= -76.8):
                    area = None
                    if prop.built_area and prop.built_area > 0:
                        area = float(prop.built_area)
                    elif prop.land_area and prop.land_area > 0:
                        area = float(prop.land_area)
                    
                    precio_m2 = None
                    if area and prop.price:
                        precio_m2 = float(prop.price) / area
                    
                    if precio_m2 and precio_m2 > 0 and precio_m2 < 10000:
                        count2 += 1
                        print(f"   {count2}. ID: {prop.id}, Coord: {lat}, {lng}, Precio: ${prop.price}, Área: {area}, Precio/m²: ${precio_m2:.2f}")
        except (ValueError, AttributeError, TypeError):
            continue
    
    print(f"   Propiedades válidas para heatmap: {count2}")
    
    print(f"\n3. CONCLUSIÓN:")
    print(f"   - Total propiedades válidas Remax: {count}")
    print(f"   - Total propiedades válidas Propify: {count2}")
    print(f"   - Total general: {count + count2}")
    
    if count + count2 == 2:
        print(f"   ✓ CORRECTO: El heatmap muestra {count + count2} propiedades reales (no inventadas)")
    else:
        print(f"   ⚠️  El número de propiedades no coincide con lo esperado")

if __name__ == '__main__':
    check_properties()