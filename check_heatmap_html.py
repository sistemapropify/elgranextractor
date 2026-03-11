import requests
import sys

try:
    response = requests.get('http://127.0.0.1:8000/market-analysis/heatmap/', timeout=5)
    html = response.text
    
    # Buscar líneas clave
    lines = html.split('\n')
    
    print("=== BUSCANDO GOOGLE MAPS API ===")
    for i, line in enumerate(lines):
        if 'google' in line.lower() and 'maps' in line.lower():
            print(f"Línea {i+1}: {line.strip()[:100]}")
    
    print("\n=== BUSCANDO heatmap.js ===")
    for i, line in enumerate(lines):
        if 'heatmap.js' in line:
            print(f"Línea {i+1}: {line.strip()[:150]}")
    
    print("\n=== BUSCANDO initHeatmapMap ===")
    for i, line in enumerate(lines):
        if 'initHeatmapMap' in line:
            print(f"Línea {i+1}: {line.strip()[:150]}")
    
    print("\n=== BUSCANDO div heatmapMap ===")
    for i, line in enumerate(lines):
        if 'heatmapMap' in line and 'id=' in line:
            print(f"Línea {i+1}: {line.strip()[:150]}")
    
    # Verificar si hay errores de JavaScript
    print("\n=== ÚLTIMAS 20 LÍNEAS DEL HTML (donde debería estar el JS) ===")
    for line in lines[-20:]:
        print(line.strip())
        
    # Guardar HTML para inspección
    with open('heatmap_debug.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("\nHTML guardado en heatmap_debug.html")
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)