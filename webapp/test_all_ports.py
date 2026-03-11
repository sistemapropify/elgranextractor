#!/usr/bin/env python
"""
Test para verificar en qué puerto está funcionando el heatmap nuevo
"""
import requests
import time

def test_port(port):
    url = f"http://localhost:{port}/market-analysis/heatmap/"
    
    try:
        response = requests.get(url, timeout=3)
        
        # Buscar indicadores
        content = response.text
        size = len(response.content)
        
        is_new_version = "HEATMAP FUNCIONAL" in content and "VERSIÓN DIRECTA HTML" in content
        has_google_maps = "maps.googleapis.com" in content
        
        return {
            'port': port,
            'status': response.status_code,
            'size': size,
            'is_new': is_new_version,
            'has_maps': has_google_maps,
            'url': url
        }
    except:
        return None

def main():
    print("Probando puertos...")
    print("-" * 60)
    
    ports = [8000, 8001, 8002]
    results = []
    
    for port in ports:
        print(f"Probando puerto {port}...")
        result = test_port(port)
        if result:
            results.append(result)
            status = "NUEVA VERSIÓN" if result['is_new'] else "VERSIÓN ANTIGUA"
            print(f"  ✓ Respuesta: {result['status']}, Tamaño: {result['size']} bytes")
            print(f"  ✓ Estado: {status}")
            if result['has_maps']:
                print(f"  ✓ Tiene Google Maps API")
            else:
                print(f"  ✗ NO tiene Google Maps API")
        else:
            print(f"  ✗ Sin respuesta")
        print()
    
    print("-" * 60)
    print("RESUMEN:")
    
    new_versions = [r for r in results if r['is_new']]
    if new_versions:
        print(f"¡ENCONTRADA VERSIÓN NUEVA en {len(new_versions)} puerto(s)!")
        for r in new_versions:
            print(f"  • Puerto {r['port']}: {r['url']}")
            print(f"    Tamaño: {r['size']} bytes, Google Maps: {'SI' if r['has_maps'] else 'NO'}")
    else:
        print("NO se encontró la versión nueva en ningún puerto.")
        print("Posibles causas:")
        print("  1. Los servidores no se recargaron correctamente")
        print("  2. Hay conflicto de puertos")
        print("  3. El cache de Django es muy persistente")
    
    # Recomendación
    print("\nRECOMENDACIÓN:")
    if new_versions:
        best_port = new_versions[0]['port']
        print(f"  Use este URL: http://localhost:{best_port}/market-analysis/heatmap/")
        print("  Abra en su navegador y verifique que el mapa se cargue.")
    else:
        print("  1. Detenga TODOS los servidores Django")
        print("  2. Ejecute solo: cd webapp && py manage.py runserver")
        print("  3. Espere a que se inicie (verá 'Starting development server')")
        print("  4. Abra: http://localhost:8000/market-analysis/heatmap/")

if __name__ == "__main__":
    main()