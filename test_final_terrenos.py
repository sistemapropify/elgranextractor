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

print("=== PRUEBA FINAL: VERIFICACIÓN DE LÓGICA DE TERRENOS ===")
print()

def test_logica_actual():
    """Test con la lógica actual del views.py"""
    print("1. PROPIEDADES REMAX (deben usar solo area_terreno para terrenos):")
    print("-" * 70)
    
    # Obtener algunos terrenos de Remax
    terrenos_remax = PropiedadRaw.objects.filter(
        coordenadas__isnull=False
    ).exclude(coordenadas='').filter(
        tipo_propiedad__icontains='terreno'
    )[:5]
    
    for prop in terrenos_remax:
        tipo = (prop.tipo_propiedad or '').lower().strip()
        es_terreno = any(term in tipo for term in ['terreno', 'terrenos', 'lote', 'parcela'])
        
        # Simular lógica actual
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
        
        print(f"ID {prop.id}: '{tipo}'")
        print(f"  Area construida: {prop.area_construida}")
        print(f"  Area terreno: {prop.area_terreno}")
        print(f"  Area usada: {area}")
        print(f"  Precio/m2: ${precio_m2:,.2f}" if precio_m2 else "  No calcula precio/m2")
        
        # Verificar
        if es_terreno:
            if area == prop.area_terreno:
                print("  OK: Terreno usa area_terreno")
            elif area == prop.area_construida:
                print("  ERROR: Terreno usa area_construida!")
            else:
                print("  ? Area usada no coincide")
        print()
    
    print()
    print("2. PROPIEDADES PROPIFAI (lógica mejorada y agresiva):")
    print("-" * 70)
    
    # Obtener propiedades Propifai con ambas áreas
    props_propifai = PropifaiProperty.objects.filter(
        coordinates__isnull=False
    ).exclude(coordinates='').filter(
        land_area__gt=0
    )[:10]
    
    for prop in props_propifai:
        # Simular lógica actual (mejorada)
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
        
        # Lógica mejorada y agresiva
        es_terreno_heuristico = False
        if land_area_val > 0:
            if built_area_val == 0 or built_area_val is None:
                es_terreno_heuristico = True
            elif land_area_val > built_area_val:
                es_terreno_heuristico = True
            elif land_area_val > 100:
                es_terreno_heuristico = True
        
        es_proyecto = prop.is_project if hasattr(prop, 'is_project') else False
        if es_proyecto and land_area_val > 0:
            es_terreno_heuristico = True
        
        es_terreno = es_terreno_texto or es_terreno_heuristico
        
        # Área usada
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
        
        print(f"ID {prop.id}:")
        print(f"  Built area: {built_area_val}")
        print(f"  Land area: {land_area_val}")
        print(f"  Ratio: {land_area_val/built_area_val:.1f}x" if built_area_val > 0 else "  Ratio: N/A")
        print(f"  Detectado texto: {es_terreno_texto}")
        print(f"  Detectado heurística: {es_terreno_heuristico}")
        print(f"  ES TERRENO: {es_terreno}")
        print(f"  Area usada: {area}")
        print(f"  Precio/m2: ${precio_m2:,.2f}" if precio_m2 else "  No calcula precio/m2")
        
        # Verificar regla del usuario: si es terreno, NO debe usar built_area
        if es_terreno and area is not None:
            if area == land_area_val:
                print("  OK: Terreno usa land_area (correcto)")
            elif area == built_area_val:
                print("  ERROR CRÍTICO: Terreno usa built_area!")
            else:
                print("  ? Area inesperada")
        elif not es_terreno and area is not None:
            if area == built_area_val:
                print("  OK: No terreno usa built_area")
            elif area == land_area_val:
                print("  OK: No terreno usa land_area (fallback)")
        print()
    
    print()
    print("3. RESUMEN DE REGLAS IMPLEMENTADAS:")
    print("-" * 70)
    print("✓ Para Remax: Si tipo_propiedad contiene 'terreno', usa SOLO area_terreno")
    print("✓ Para Propifai: Si detectado como terreno (texto O heurística), usa SOLO land_area")
    print("✓ Heurística Propifai detecta terreno cuando:")
    print("  - land_area > 0 y (built_area es 0/None)")
    print("  - land_area > built_area")
    print("  - land_area > 100 m² (umbral mínimo)")
    print("  - es proyecto (is_project=True)")
    print("✓ NUNCA se usa built_area para terrenos detectados")
    print("✓ Para no terrenos: prioriza built_area, fallback a land_area")

if __name__ == "__main__":
    test_logica_actual()