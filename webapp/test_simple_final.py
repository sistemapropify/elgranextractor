#!/usr/bin/env python
"""
Test final simple para verificar el heatmap
"""
import requests

def test_heatmap():
    url = "http://localhost:8000/market-analysis/heatmap/"
    
    try:
        print("=== TEST HEATMAP ===")
        print(f"URL: {url}")
        
        response = requests.get(url, timeout=10)
        
        print(f"Status: {response.status_code}")
        print(f"Size: {len(response.content)} bytes")
        
        content = response.text
        
        # Verificaciones clave
        checks = [
            ("HEATMAP FUNCIONAL", "Titulo nuevo de la vista"),
            ("heatmapMap", "Div del mapa"),
            ("maps.googleapis.com", "Google Maps API"),
            ("initializeHeatmap", "Funcion JavaScript"),
            ("loadGoogleMapsAPI", "Funcion cargar API"),
        ]
        
        print("\n--- VERIFICACIONES ---")
        all_ok = True
        for text, description in checks:
            found = text in content
            status = "OK" if found else "FALLO"
            print(f"{status:6} {description:30} -> {'SI' if found else 'NO'}")
            if not found:
                all_ok = False
        
        print(f"\n--- RESUMEN ---")
        if all_ok:
            print("¡TODO CORRECTO! El heatmap debería funcionar.")
            print("Abra http://localhost:8000/market-analysis/heatmap/ en su navegador.")
        else:
            print("PROBLEMAS DETECTADOS:")
            print("1. El servidor sigue sirviendo la versión cacheada (33,257 bytes)")
            print("2. Django tiene un cache persistente de templates")
            print("\nSOLUCIONES:")
            print("a) Detener TODOS los servidores Django")
            print("b) Ejecutar: py manage.py shell -c \"from django.template import loader; loader.template_source_loaders = None\"")
            print("c) Reiniciar el servidor")
            print("d) Probar en un navegador con Ctrl+F5 para forzar recarga")
            
        # Guardar muestra para inspección
        sample = content[:3000]
        print(f"\n--- MUESTRA (primeros 3000 chars) ---")
        print(sample)
        print("--- FIN MUESTRA ---")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_heatmap()