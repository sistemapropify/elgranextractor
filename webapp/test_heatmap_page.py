#!/usr/bin/env python
"""
Test para verificar si el template heatmap.html se está sirviendo correctamente
"""
import requests
import sys

def test_heatmap_page():
    url = "http://localhost:8000/market-analysis/heatmap/"
    
    try:
        print(f"Probando URL: {url}")
        response = requests.get(url, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Content Length: {len(response.content)} bytes")
        
        # Verificar si contiene el JavaScript esperado
        content = response.text
        
        # Buscar indicadores clave
        indicators = {
            "Google Maps API": "maps.googleapis.com/maps/api/js" in content,
            "initHeatmap function": "function initializeHeatmap()" in content,
            "loadGoogleMapsAPI function": "function loadGoogleMapsAPI()" in content,
            "heatmapMap div": 'id="heatmapMap"' in content,
            "JavaScript script tag": "<script>" in content and "</script>" in content,
        }
        
        print("\nIndicadores encontrados:")
        for key, found in indicators.items():
            status = "✓" if found else "✗"
            print(f"  {status} {key}")
        
        # Guardar una muestra del contenido para inspección
        sample_size = min(5000, len(content))
        print(f"\nPrimeros {sample_size} caracteres del contenido:")
        print("-" * 50)
        print(content[:sample_size])
        print("-" * 50)
        
        # Guardar el contenido completo para análisis
        with open("heatmap_test_output.html", "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\nContenido completo guardado en: heatmap_test_output.html")
        
        # Análisis de tamaño
        if len(response.content) > 35000:
            print(f"\n⚠️  ADVERTENCIA: El contenido tiene {len(response.content)} bytes, lo que sugiere que")
            print("   todavía se está sirviendo la versión antigua del template (33,257 bytes).")
            print("   La versión nueva debería tener alrededor de 6,590 bytes.")
        else:
            print(f"\n✅ El contenido tiene {len(response.content)} bytes, lo que sugiere que")
            print("   se está sirviendo la versión nueva del template.")
            
    except requests.exceptions.ConnectionError:
        print("❌ Error de conexión. Asegúrese de que el servidor Django esté corriendo.")
        print("   Ejecute: cd webapp && py manage.py runserver")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_heatmap_page()