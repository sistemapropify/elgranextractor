#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty

print("=== DEBUG: PROPIEDADES PROPIFAI CON BUILT_AREA > 0 ===")
print()

# Buscar propiedades que podrían ser terrenos pero tienen built_area
props = PropifaiProperty.objects.filter(
    coordinates__isnull=False
).exclude(coordinates='').filter(
    land_area__gt=0
)[:50]

for prop in props:
    description = (prop.description or '').lower().strip()
    title = (prop.title or '').lower().strip()
    zoning = (prop.zoning or '').lower().strip()
    
    textos_busqueda = f'{description} {title} {zoning}'
    es_terreno_texto = any(term in textos_busqueda for term in [
        'terreno', 'terrenos', 'lote', 'parcela', 'parcel',
        'land', 'lot', 'plot', 'ground', 'solar', 'vacant'
    ])
    
    built_area_val = prop.built_area if prop.built_area else 0
    land_area_val = prop.land_area if prop.land_area else 0
    
    es_terreno_heuristico = (built_area_val == 0 or built_area_val is None) and land_area_val > 0
    
    # Lógica actual
    es_terreno = es_terreno_texto or es_terreno_heuristico
    
    # Qué área usaría
    area_usada = None
    if es_terreno:
        if prop.land_area and prop.land_area > 0:
            area_usada = prop.land_area
    else:
        if prop.built_area and prop.built_area > 0:
            area_usada = prop.built_area
        elif prop.land_area and prop.land_area > 0:
            area_usada = prop.land_area
    
    # Mostrar solo si hay posible problema
    if es_terreno_texto and built_area_val > 0:
        print(f"ID {prop.id}:")
        print(f"  Detectado por texto como terreno: SÍ")
        print(f"  Heurística dice terreno: {es_terreno_heuristico}")
        print(f"  Resultado final: {'TERRENO' if es_terreno else 'NO TERRENO'}")
        print(f"  Built area: {built_area_val}")
        print(f"  Land area: {land_area_val}")
        print(f"  Área que se usaría: {area_usada}")
        print(f"  Textos: desc='{description[:50]}...', title='{title[:50]}...', zoning='{zoning}'")
        print()

print()
print("=== PROPIEDADES CON 'terreno' EN TEXTO ===")
print()

# Buscar específicamente por texto
for prop in PropifaiProperty.objects.filter(
    coordinates__isnull=False
).exclude(coordinates='')[:100]:
    description = (prop.description or '').lower()
    title = (prop.title or '').lower()
    zoning = (prop.zoning or '').lower()
    
    if any(term in description or term in title or term in zoning 
           for term in ['terreno', 'terrenos', 'lote', 'parcela']):
        print(f"ID {prop.id}:")
        print(f"  Description: '{description[:100]}...'")
        print(f"  Title: '{title[:100]}...'")
        print(f"  Zoning: '{zoning}'")
        print(f"  Built area: {prop.built_area}")
        print(f"  Land area: {prop.land_area}")
        print()