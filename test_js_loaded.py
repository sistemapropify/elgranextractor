#!/usr/bin/env python3
import urllib.request

url = 'http://127.0.0.1:8000/market-analysis/heatmap/'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req)
html = response.read().decode('utf-8')

print("=== VERIFICANDO SI JAVASCRIPT SE CARGA ===")

# Buscar scripts clave
scripts_to_find = [
    ('maps.googleapis.com', 'Google Maps API'),
    ('market_analysis/js/heatmap.js', 'heatmap.js'),
    ('AIzaSy', 'Clave API de Google'),
    ('initHeatmapMap', 'Función initHeatmapMap')
]

found_count = 0
for pattern, description in scripts_to_find:
    if pattern in html:
        found_count += 1
        print(f"OK - Encontrado: {description}")
    else:
        print(f"NO - NO encontrado: {description}")

print(f"\nTotal encontrados: {found_count}/{len(scripts_to_find)}")

if found_count == len(scripts_to_find):
    print("\n✅ TODO el JavaScript necesario está en el HTML.")
    print("   El mapa de Google Maps debería cargarse correctamente.")
elif found_count >= 2:
    print(f"\n⚠️  {found_count}/{len(scripts_to_find)} scripts encontrados.")
    print("   Algunos componentes pueden faltar.")
else:
    print("\n❌ Muy poco JavaScript encontrado.")
    print("   El mapa NO se cargará correctamente.")

# Verificar también si hay errores comunes
if 'Error al cargar Google Maps' in html:
    print("\n⚠️  ADVERTENCIA: El HTML contiene mensajes de error de Google Maps")

print("\n=== RECOMENDACIÓN ===")
print("1. Abrir http://127.0.0.1:8000/market-analysis/heatmap/ en un navegador")
print("2. Presionar F12 para abrir las herramientas de desarrollador")
print("3. Verificar la consola para errores de JavaScript")
print("4. Si hay errores, verificar:")
print("   - Que la clave API de Google Maps sea válida")
print("   - Que el archivo heatmap.js exista en static/market_analysis/js/")
print("   - Que no haya errores de CORS o red")