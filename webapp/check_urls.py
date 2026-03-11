#!/usr/bin/env python
"""
Verificar URLs del market_analysis
"""
import requests

def check_urls():
    base_url = "http://localhost:8000/market-analysis/"
    
    urls = [
        "heatmap/",
        "heatmap-simple/", 
        "heatmap-test/",
        "dashboard/",
    ]
    
    for url_suffix in urls:
        url = base_url + url_suffix
        try:
            response = requests.get(url, timeout=5)
            print(f"{url_suffix:20} -> Status: {response.status_code}, Size: {len(response.content)} bytes")
            
            if response.status_code == 200:
                # Verificar contenido básico
                content = response.text
                if "heatmapMap" in content:
                    print(f"  ✓ Contiene 'heatmapMap'")
                if "maps.googleapis.com" in content:
                    print(f"  ✓ Contiene Google Maps API")
                if "<script>" in content:
                    print(f"  ✓ Contiene JavaScript")
                    
        except requests.exceptions.ConnectionError:
            print(f"{url_suffix:20} -> ERROR: No se pudo conectar")
        except Exception as e:
            print(f"{url_suffix:20} -> ERROR: {e}")

if __name__ == "__main__":
    check_urls()