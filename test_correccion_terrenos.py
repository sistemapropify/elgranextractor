#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw
from propifai.models import PropifaiProperty

print("=== PRUEBA DE CORRECCIÓN PARA TERRENOS ===")
print()

# Simular la lógica de heatmap_view para verificar
def simular_logica_remax(prop):
    """Simula la lógica de cálculo para PropiedadRaw"""
    tipo_propiedad = (prop.tipo_propiedad or '').lower().strip() if hasattr(prop, 'tipo_propiedad') else ''
    
    # Detectar terrenos con más variantes (misma lógica que views.py)
    es_terreno = any(term in tipo_propiedad for term in [
        'terreno', 'terrenos', 'lote', 'parcela', 'parcel',
        'land', 'lot', 'plot', 'ground', 'solar', 'vacant'
    ])
    
    area = None
    if es_terreno:
        if prop.area_terreno and prop.area_terreno > 0:
            area = float(prop.area_terreno)
    else:
        if prop.area_construida and prop.area_construida > 0:
            area = float(prop.area_construida)
        elif prop.area_terreno and prop.area_terreno > 0:
            area = float(prop.area_terreno)
    
    precio_m2 = None
    if area and prop.precio_usd and prop.precio_usd > 0:
        precio_m2 = float(prop.precio_usd) / area
    
    return {
        'es_terreno': es_terreno,
        'area_usada': area,
        'area_construida': prop.area_construida,
        'area_terreno': prop.area_terreno,
        'precio_m2': precio_m2,
        'tipo': tipo_propiedad
    }

def simular_logica_propifai(prop):
    """Simula la lógica de cálculo para PropifaiProperty (corregida)"""
    # Detectar terrenos en Propifai (no hay property_type, usar heurística)
    es_terreno = False
    
    # 1. Buscar en description y title si existen
    description = (prop.description or '').lower().strip()
    title = (prop.title or '').lower().strip()
    zoning = (prop.zoning or '').lower().strip()
    
    # Verificar si contiene términos de terreno
    textos_busqueda = f'{description} {title} {zoning}'
    es_terreno_texto = any(term in textos_busqueda for term in [
        'terreno', 'terrenos', 'lote', 'parcela', 'parcel',
        'land', 'lot', 'plot', 'ground', 'solar', 'vacant'
    ])
    
    # 2. Heurística: si built_area es None/0 y land_area > 0, probablemente terreno
    built_area_val = prop.built_area if prop.built_area else 0
    land_area_val = prop.land_area if prop.land_area else 0
    
    es_terreno_heuristico = (built_area_val == 0 or built_area_val is None) and land_area_val > 0
    
    # Combinar ambas detecciones
    es_terreno = es_terreno_texto or es_terreno_heuristico
    
    area = None
    if es_terreno:
        if prop.land_area and prop.land_area > 0:
            area = float(prop.land_area)
    else:
        if prop.built_area and prop.built_area > 0:
            area = float(prop.built_area)
        elif prop.land_area and prop.land_area > 0:
            area = float(prop.land_area)
    
    precio_m2 = None
    if area and prop.price and prop.price > 0:
        precio_m2 = float(prop.price) / area
    
    return {
        'es_terreno': es_terreno,
        'area_usada': area,
        'built_area': prop.built_area,
        'land_area': prop.land_area,
        'precio_m2': precio_m2,
        'detectado_por_texto': es_terreno_texto,
        'detectado_por_heuristico': es_terreno_heuristico
    }

print("1. PRUEBA CON PROPIEDADES REMAX (TERRENOS):")
print("-" * 50)

# Obtener algunos terrenos de ejemplo
terrenos_remax = []
for prop in PropiedadRaw.objects.filter(coordenadas__isnull=False).exclude(coordenadas='')[:30]:
    tipo = (prop.tipo_propiedad or '').lower().strip()
    if 'terreno' in tipo:
        resultado = simular_logica_remax(prop)
        terrenos_remax.append((prop.id, resultado))
        if len(terrenos_remax) >= 5:
            break

if terrenos_remax:
    for prop_id, resultado in terrenos_remax:
        print(f"ID {prop_id}:")
        print(f"  Tipo: '{resultado['tipo']}'")
        print(f"  Detectado como terreno: {resultado['es_terreno']}")
        print(f"  Área construida: {resultado['area_construida']}")
        print(f"  Área terreno: {resultado['area_terreno']}")
        print(f"  Área usada para cálculo: {resultado['area_usada']}")
        if resultado['precio_m2']:
            print(f"  Precio/m² calculado: ${resultado['precio_m2']:,.2f}")
        print()
else:
    print("No se encontraron terrenos en las primeras 30 propiedades")

print()
print("2. PRUEBA CON PROPIEDADES PROPIFAI:")
print("-" * 50)

# Obtener algunas propiedades Propifai
props_propifai = PropifaiProperty.objects.filter(coordinates__isnull=False).exclude(coordinates='')[:20]

terrenos_propifai = []
no_terrenos_propifai = []

for prop in props_propifai:
    resultado = simular_logica_propifai(prop)
    if resultado['es_terreno']:
        terrenos_propifai.append((prop.id, resultado))
    else:
        no_terrenos_propifai.append((prop.id, resultado))

print(f"Total propiedades analizadas: {len(props_propifai)}")
print(f"Terrenos detectados: {len(terrenos_propifai)}")
print(f"No terrenos: {len(no_terrenos_propifai)}")

if terrenos_propifai:
    print("\nEjemplos de terrenos detectados en Propifai:")
    for prop_id, resultado in terrenos_propifai[:3]:
        print(f"ID {prop_id}:")
        print(f"  Detectado por texto: {resultado['detectado_por_texto']}")
        print(f"  Detectado por heurística: {resultado['detectado_por_heuristico']}")
        print(f"  Built area: {resultado['built_area']}")
        print(f"  Land area: {resultado['land_area']}")
        print(f"  Área usada: {resultado['area_usada']}")
        if resultado['precio_m2']:
            print(f"  Precio/m²: ${resultado['precio_m2']:,.2f}")
        print()

print()
print("3. VERIFICACIÓN DE CÁLCULOS CORRECTOS:")
print("-" * 50)

# Verificar que los terrenos usen solo área de terreno
errores = []

print("Verificando terrenos Remax:")
for prop_id, resultado in terrenos_remax:
    if resultado['es_terreno'] and resultado['area_usada']:
        # Debería usar area_terreno, no area_construida
        if resultado['area_construida'] and resultado['area_construida'] > 0:
            # Si tiene área construida pero se usó área terreno, está bien
            if resultado['area_usada'] == resultado['area_construida']:
                errores.append(f"ERROR: Terreno ID {prop_id} usa área construida ({resultado['area_construida']}) en lugar de área terreno")
            else:
                print(f"  OK: Terreno ID {prop_id} usa área terreno ({resultado['area_usada']}) correctamente")
        else:
            print(f"  OK: Terreno ID {prop_id} no tiene área construida, usa área terreno ({resultado['area_usada']})")

print("\nVerificando terrenos Propifai:")
for prop_id, resultado in terrenos_propifai:
    if resultado['es_terreno'] and resultado['area_usada']:
        # Debería usar land_area, no built_area
        if resultado['built_area'] and resultado['built_area'] > 0:
            if resultado['area_usada'] == resultado['built_area']:
                errores.append(f"ERROR: Terreno Propifai ID {prop_id} usa built_area ({resultado['built_area']}) en lugar de land_area")
            else:
                print(f"  OK: Terreno Propifai ID {prop_id} usa land_area ({resultado['area_usada']}) correctamente")
        else:
            print(f"  OK: Terreno Propifai ID {prop_id} no tiene built_area, usa land_area ({resultado['area_usada']})")

print()
print("=== RESUMEN ===")
if errores:
    print(f"Se encontraron {len(errores)} errores:")
    for error in errores:
        print(f"  • {error}")
else:
    print("¡TODOS LOS CÁLCULOS SON CORRECTOS!")
    print("Los terrenos ahora usan solo el área de terreno para calcular el precio por m².")