#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty

print("=== PRUEBA DE LÓGICA MEJORADA PARA TERRENOS PROPIFAI ===")
print()

def simular_logica_mejorada(prop):
    """Simula la nueva lógica mejorada"""
    # 1. Buscar en description, title, zoning
    description = (prop.description or '').lower().strip()
    title = (prop.title or '').lower().strip()
    zoning = (prop.zoning or '').lower().strip()
    
    # Verificar si contiene términos de terreno
    textos_busqueda = f'{description} {title} {zoning}'
    es_terreno_texto = any(term in textos_busqueda for term in [
        'terreno', 'terrenos', 'lote', 'parcela', 'parcel',
        'land', 'lot', 'plot', 'ground', 'solar', 'vacant'
    ])
    
    # 2. Heurística mejorada: si land_area existe y es el área principal
    built_area_val = prop.built_area if prop.built_area else 0
    land_area_val = prop.land_area if prop.land_area else 0
    
    # Si tiene land_area y es claramente un terreno (por texto), es terreno
    # Si no hay texto pero land_area es significativamente mayor que built_area, probablemente terreno
    # Ej: land_area=1000, built_area=4 (caseta) -> es terreno
    es_terreno_heuristico = False
    if land_area_val > 0:
        if built_area_val == 0 or built_area_val is None:
            es_terreno_heuristico = True
        elif land_area_val > built_area_val * 5:  # land_area es 5x mayor que built_area
            es_terreno_heuristico = True
    
    # 3. Si es proyecto (is_project=True) y tiene land_area, probablemente terreno para desarrollo
    es_proyecto = prop.is_project if hasattr(prop, 'is_project') else False
    if es_proyecto and land_area_val > 0:
        es_terreno_heuristico = True
    
    # Combinar detecciones - si cualquiera dice que es terreno, lo tratamos como terreno
    es_terreno = es_terreno_texto or es_terreno_heuristico
    
    # SI ES TERRENO: usar SOLO land_area (nunca built_area)
    area = None
    if es_terreno:
        if prop.land_area and prop.land_area > 0:
            area = float(prop.land_area)
        # Si no hay land_area, NO usar built_area bajo ninguna circunstancia
    else:
        # Para NO terrenos, priorizar built_area con fallback a land_area
        if prop.built_area and prop.built_area > 0:
            area = float(prop.built_area)
        elif prop.land_area and prop.land_area > 0:
            area = float(prop.land_area)
    
    precio_m2 = None
    if area and prop.price and prop.price > 0:
        precio_m2 = float(prop.price) / area
    
    return {
        'es_terreno': es_terreno,
        'es_terreno_texto': es_terreno_texto,
        'es_terreno_heuristico': es_terreno_heuristico,
        'area_usada': area,
        'built_area': built_area_val,
        'land_area': land_area_val,
        'precio_m2': precio_m2,
        'ratio_land_built': land_area_val / built_area_val if built_area_val > 0 else float('inf')
    }

# Analizar propiedades con built_area > 0 y land_area > 0
print("1. PROPIEDADES CON AMBAS ÁREAS (posibles terrenos con construcciones pequeñas):")
print("-" * 80)

props_mixtas = PropifaiProperty.objects.filter(
    coordinates__isnull=False
).exclude(coordinates='').filter(
    built_area__gt=0,
    land_area__gt=0
)[:15]

for prop in props_mixtas:
    resultado = simular_logica_mejorada(prop)
    
    # Solo mostrar si es interesante
    if resultado['land_area'] > resultado['built_area']:
        print(f"ID {prop.id}:")
        print(f"  Built area: {resultado['built_area']}")
        print(f"  Land area: {resultado['land_area']}")
        print(f"  Ratio land/built: {resultado['ratio_land_built']:.1f}x")
        print(f"  Detectado por texto: {resultado['es_terreno_texto']}")
        print(f"  Detectado por heurística: {resultado['es_terreno_heuristico']}")
        print(f"  ES TERRENO: {resultado['es_terreno']}")
        print(f"  Área usada: {resultado['area_usada']}")
        if resultado['precio_m2']:
            print(f"  Precio/m²: ${resultado['precio_m2']:,.2f}")
        
        # Verificar lógica
        if resultado['es_terreno']:
            if resultado['area_usada'] == resultado['land_area']:
                print(f"  ✓ CORRECTO: Usa land_area para terreno")
            else:
                print(f"  ✗ ERROR: Debería usar land_area pero usa {resultado['area_usada']}")
        else:
            if resultado['area_usada'] == resultado['built_area']:
                print(f"  ✓ CORRECTO: No es terreno, usa built_area")
            else:
                print(f"  ? Usa {resultado['area_usada']}")
        print()

print()
print("2. CASOS CRÍTICOS (terrenos con construcciones pequeñas):")
print("-" * 80)

# Simular casos hipotéticos
casos_criticos = [
    {'id': 'C1', 'land_area': 1000, 'built_area': 4, 'desc': 'terreno con caseta'},
    {'id': 'C2', 'land_area': 500, 'built_area': 50, 'desc': 'terreno con construcción pequeña'},
    {'id': 'C3', 'land_area': 200, 'built_area': 180, 'desc': 'casa con jardín'},
    {'id': 'C4', 'land_area': 300, 'built_area': 0, 'desc': 'terreno vacío'},
    {'id': 'C5', 'land_area': 150, 'built_area': 150, 'desc': 'casa que ocupa todo el terreno'},
]

for caso in casos_criticos:
    # Simular propiedad
    class PropSimulada:
        pass
    
    prop = PropSimulada()
    prop.id = caso['id']
    prop.description = caso['desc']
    prop.title = ''
    prop.zoning = ''
    prop.built_area = caso['built_area']
    prop.land_area = caso['land_area']
    prop.price = 100000  # precio ejemplo
    prop.is_project = False
    
    resultado = simular_logica_mejorada(prop)
    
    print(f"Caso {caso['id']}: {caso['desc']}")
    print(f"  Land: {caso['land_area']} m², Built: {caso['built_area']} m²")
    print(f"  Ratio: {caso['land_area']/caso['built_area'] if caso['built_area']>0 else '∞':.1f}x")
    print(f"  Es terreno: {resultado['es_terreno']} (texto: {resultado['es_terreno_texto']}, heur: {resultado['es_terreno_heuristico']})")
    print(f"  Área usada: {resultado['area_usada']} m²")
    print(f"  Precio/m²: ${resultado['precio_m2']:,.2f}" if resultado['precio_m2'] else "  No calcula precio/m²")
    print()

print()
print("=== CONCLUSIÓN ===")
print("La nueva lógica detecta como terreno cuando:")
print("1. Contiene términos como 'terreno', 'lote', etc. en description/title/zoning")
print("2. land_area > 0 y (built_area es 0/None O land_area > built_area * 5)")
print("3. Es proyecto (is_project=True) y tiene land_area")
print()
print("Para terrenos detectados, SOLO se usa land_area (nunca built_area).")
print("Esto resuelve el problema de terrenos con construcciones pequeñas (caseta de 2x2m).")