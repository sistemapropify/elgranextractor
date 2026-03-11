#!/usr/bin/env python3
import urllib.request

url = 'http://127.0.0.1:8000/market-analysis/heatmap/'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req)
html = response.read().decode('utf-8')

# Buscar estilos específicos del heatmap
print("=== BUSCANDO ESTILOS DEL HEATMAP EN HTML ===")

# Buscar clases CSS específicas
classes_to_find = [
    'heatmap-container',
    'heatmap-card',
    'heatmap-map',
    'stats-card',
    'filter-section'
]

found_count = 0
for class_name in classes_to_find:
    if class_name in html:
        found_count += 1
        print(f"✅ Encontrada clase: {class_name}")
    else:
        print(f"❌ NO encontrada clase: {class_name}")

print(f"\nTotal encontradas: {found_count}/{len(classes_to_find)}")

if found_count > 0:
    print("\n✅ El CSS del heatmap SÍ está en el HTML renderizado.")
    print("   Esto significa que el bloque extra_css SÍ se está insertando.")
    print("\nPROBLEMA: Solo el bloque extra_js no se está insertando.")
else:
    print("\n❌ El CSS del heatmap NO está en el HTML renderizado.")
    print("   Esto significa que NI extra_css NI extra_js se están insertando.")
    print("   El problema es con la herencia completa del template.")