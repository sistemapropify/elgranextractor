#!/usr/bin/env python
"""
Test con headers para evitar cache
"""
import requests

def test_no_cache():
    url = "http://localhost:8000/market-analysis/heatmap/"
    
    headers = {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
    }
    
    try:
        print(f"Probando URL: {url}")
        print(f"Con headers anti-cache...")
        
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Content Length: {len(response.content)} bytes")
        
        # Buscar texto específico
        content = response.text
        
        # Buscar el título nuevo
        if "HEATMAP FUNCIONAL" in content:
            print("✓ ¡ENCONTRADO! La página muestra 'HEATMAP FUNCIONAL'")
            print("  Esto significa que la vista nueva está funcionando.")
        else:
            print("✗ NO encontrado 'HEATMAP FUNCIONAL'")
            print("  La página sigue siendo la versión antigua.")
            
        # Buscar JavaScript de Google Maps
        if "maps.googleapis.com" in content:
            print("✓ Contiene Google Maps API")
        else:
            print("✗ NO contiene Google Maps API")
            
        # Buscar el div del mapa
        if 'id="heatmapMap"' in content:
            print("✓ Contiene div heatmapMap")
        else:
            print("✗ NO contiene div heatmapMap")
            
        # Guardar una muestra
        with open("heatmap_latest.html", "w", encoding="utf-8") as f:
            f.write(content[:5000])
        print(f"\nMuestra guardada en heatmap_latest.html (primeros 5000 chars)")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_no_cache()