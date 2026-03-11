#!/usr/bin/env python
"""
Test para verificar si el template heatmap_simple.html funciona
"""
import requests
import sys

def test_heatmap_simple():
    url = "http://localhost:8000/market-analysis/heatmap/"
    
    try:
        print(f"Probando URL: {url}")
        response = requests.get(url, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Content Length: {len(response.content)} bytes")
        
        # Verificar si contiene elementos clave
        content = response.text
        
        # Buscar indicadores clave
        indicators = {
            "Google Maps API": "maps.googleapis.com/maps/api/js" in content,
            "heatmapMap div": 'id="heatmapMap"' in content,
            "JavaScript script tag": "<script>" in content and "</script>" in content,
            "initializeHeatmap function": "function initializeHeatmap()" in content,
            "loadGoogleMapsAPI function": "function loadGoogleMapsAPI()" in content,
        }
        
        print("\nIndicadores encontrados:")
        for key, found in indicators.items():
            status = "[OK]" if found else "[NO]"
            print(f"  {status} {key}")
        
        # Guardar una muestra del contenido
        sample_size = min(2000, len(content))
        print(f"\nPrimeros {sample_size} caracteres del contenido:")
        print("-" * 50)
        print(content[:sample_size])
        print("-" * 50)
        
        # Análisis de tamaño
        print(f"\nAnalisis de tamaño:")
        print(f"  - Contenido total: {len(response.content)} bytes")
        
        if len(response.content) < 10000:
            print(f"  [ADVERTENCIA] El contenido es muy pequeño ({len(response.content)} bytes)")
            print(f"  Podría estar vacío o incompleto.")
        elif len(response.content) > 50000:
            print(f"  [ADVERTENCIA] El contenido es muy grande ({len(response.content)} bytes)")
            print(f"  Podría ser la versión antigua cacheada.")
        else:
            print(f"  [OK] Tamaño razonable para un template simple")
            
        # Verificar si hay errores de JavaScript
        if "SyntaxError" in content or "ReferenceError" in content:
            print(f"\n[ERROR] Se detectaron errores de JavaScript en el HTML")
        else:
            print(f"\n[OK] No se detectaron errores de JavaScript obvios")
            
    except requests.exceptions.ConnectionError:
        print("[ERROR] Error de conexión. Asegúrese de que el servidor Django esté corriendo.")
        print("   Ejecute: cd webapp && py manage.py runserver")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_heatmap_simple()