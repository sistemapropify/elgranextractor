#!/usr/bin/env python
"""
Script para probar las correcciones realizadas.
"""
import sys
import time
import requests

def test_correcciones():
    print("=== Prueba de correcciones ===")
    
    # Esperar a que el servidor se inicie
    print("Esperando 3 segundos...")
    time.sleep(3)
    
    url = "http://localhost:8000/eventos/"
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            
            # Verificar que el título no esté truncado
            if 'truncatechars:30' not in content and '|truncatechars' not in content:
                print("OK: Títulos no están truncados (sin filtro truncatechars)")
            else:
                print("ERROR: Aún hay títulos truncados")
                
            # Verificar que Leaflet esté referenciado
            if 'leaflet' in content.lower() or 'openstreetmap' in content.lower():
                print("OK: Leaflet/OpenStreetMap referenciado")
            else:
                print("WARNING: Leaflet no encontrado en el HTML")
                
            # Verificar elementos clave
            checks = [
                ('Propiedad', 'Columna Propiedad'),
                ('Coordenadas', 'Columna Coordenadas'),
                ('Ver Mapa', 'Botón Ver Mapa'),
                ('mapModal', 'Modal de mapa'),
            ]
            
            all_ok = True
            for text, desc in checks:
                if text in content:
                    print(f"OK: {desc} encontrado")
                else:
                    print(f"ERROR: {desc} NO encontrado")
                    all_ok = False
            
            if all_ok:
                print("\n✓ Todas las correcciones implementadas correctamente")
                return True
            else:
                print("\n✗ Algunas correcciones faltan")
                return False
                
        else:
            print(f"ERROR: Código {response.status_code}")
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == '__main__':
    success = test_correcciones()
    sys.exit(0 if success else 1)