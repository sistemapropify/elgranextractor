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

print("=== INVESTIGACIÓN DE TERRENOS EN HEATMAP ===")
print()

# 1. Ver valores únicos de tipo_propiedad en PropiedadRaw
print("1. VALORES ÚNICOS DE tipo_propiedad (Remax):")
tipos_raw = PropiedadRaw.objects.exclude(tipo_propiedad__isnull=True).exclude(tipo_propiedad='').values_list('tipo_propiedad', flat=True).distinct()
tipos_list = list(tipos_raw)
print(f"   Total de valores distintos: {len(tipos_list)}")
for i, tipo in enumerate(tipos_list[:30]):
    print(f"   [{i+1}] \"{tipo}\"")
if len(tipos_list) > 30:
    print(f"   ... y {len(tipos_list)-30} más")

print()

# 2. Analizar detección de terrenos en PropiedadRaw
print("2. DETECCIÓN DE TERRENOS EN PROPIEDADES REMAX:")
props_raw = PropiedadRaw.objects.filter(coordenadas__isnull=False).exclude(coordenadas='')[:100]
terrenos_raw = []
no_terrenos_raw = []

for prop in props_raw:
    tipo = (prop.tipo_propiedad or '').lower().strip()
    es_terreno = any(term in tipo for term in ['terreno', 'terrenos', 'lote', 'parcela', 'parcel', 'land', 'lot', 'plot', 'ground', 'solar', 'vacant'])
    
    if es_terreno:
        terrenos_raw.append({
            'id': prop.id,
            'tipo': tipo,
            'area_construida': prop.area_construida,
            'area_terreno': prop.area_terreno,
            'precio_usd': prop.precio_usd
        })
    else:
        no_terrenos_raw.append(tipo)

print(f"   Propiedades analizadas: {len(props_raw)}")
print(f"   Terrenos detectados: {len(terrenos_raw)}")
print(f"   No terrenos: {len(no_terrenos_raw)}")

if terrenos_raw:
    print("   Ejemplos de terrenos detectados:")
    for i, t in enumerate(terrenos_raw[:5]):
        print(f"   - ID {t['id']}: tipo=\"{t['tipo']}\", area_construida={t['area_construida']}, area_terreno={t['area_terreno']}, precio={t['precio_usd']}")
else:
    print("   No se encontraron terrenos en las primeras 100 propiedades con coordenadas.")

print()

# 3. Ver valores únicos de property_type en PropifaiProperty
print("3. VALORES ÚNICOS DE property_type (Propifai):")
tipos_propifai = PropifaiProperty.objects.exclude(property_type__isnull=True).exclude(property_type='').values_list('property_type', flat=True).distinct()
tipos_propifai_list = list(tipos_propifai)
print(f"   Total de valores distintos: {len(tipos_propifai_list)}")
for i, tipo in enumerate(tipos_propifai_list[:30]):
    print(f"   [{i+1}] \"{tipo}\"")
if len(tipos_propifai_list) > 30:
    print(f"   ... y {len(tipos_propifai_list)-30} más")

print()

# 4. Analizar detección de terrenos en PropifaiProperty
print("4. DETECCIÓN DE TERRENOS EN PROPIEDADES PROPIFAI:")
props_propifai = PropifaiProperty.objects.filter(coordinates__isnull=False).exclude(coordinates='')[:100]
terrenos_propifai = []
no_terrenos_propifai = []

for prop in props_propifai:
    tipo = (prop.property_type or '').lower().strip()
    es_terreno = any(term in tipo for term in ['terreno', 'terrenos', 'lote', 'parcela', 'parcel', 'land', 'lot', 'plot', 'ground', 'solar', 'vacant'])
    
    if es_terreno:
        terrenos_propifai.append({
            'id': prop.id,
            'tipo': tipo,
            'built_area': prop.built_area,
            'land_area': prop.land_area,
            'price': prop.price
        })
    else:
        no_terrenos_propifai.append(tipo)

print(f"   Propiedades analizadas: {len(props_propifai)}")
print(f"   Terrenos detectados: {len(terrenos_propifai)}")
print(f"   No terrenos: {len(no_terrenos_propifai)}")

if terrenos_propifai:
    print("   Ejemplos de terrenos detectados:")
    for i, t in enumerate(terrenos_propifai[:5]):
        print(f"   - ID {t['id']}: tipo=\"{t['tipo']}\", built_area={t['built_area']}, land_area={t['land_area']}, price={t['price']}")
else:
    print("   No se encontraron terrenos en las primeras 100 propiedades con coordenadas.")

print()

# 5. Verificar lógica de cálculo de precio/m²
print("5. VERIFICACIÓN DE LÓGICA DE CÁLCULO:")
print("   Para terrenos detectados, el área usada debería ser:")
print("   - Remax: area_terreno (no area_construida)")
print("   - Propifai: land_area (no built_area)")

if terrenos_raw:
    print("   Ejemplo de cálculo para terreno Remax:")
    t = terrenos_raw[0]
    if t['area_terreno'] and t['area_terreno'] > 0 and t['precio_usd'] and t['precio_usd'] > 0:
        precio_m2 = t['precio_usd'] / t['area_terreno']
        print(f"     Precio: ${t['precio_usd']:,}")
        print(f"     Área terreno: {t['area_terreno']} m²")
        print(f"     Precio/m²: ${precio_m2:,.2f}")
    else:
        print(f"     No se puede calcular (área={t['area_terreno']}, precio={t['precio_usd']})")

print()
print("=== FIN DEL ANÁLISIS ===")