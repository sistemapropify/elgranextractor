#!/usr/bin/env python3
"""
Prueba simple para verificar la leyenda interactiva.
"""

import requests
import re

def test_simple():
    url = "http://127.0.0.1:8000/eventos/"
    
    try:
        print("Probando conexión al servidor...")
        response = requests.get(url, timeout=5)
        print(f"Estado: {response.status_code}")
        
        if response.status_code == 200:
            html = response.text
            
            # Verificaciones básicas
            checks = [
                ("Chart.js CDN", 'cdn.jsdelivr.net/npm/chart.js' in html),
                ("Canvas del gráfico", 'id="evolucionTiposChart"' in html),
                ("Leyenda interactiva", 'legend:' in html and 'display: true' in html),
                ("Función onClick", 'onClick:' in html and 'legendItem' in html),
                ("Texto instructivo", 'Haz clic en los elementos de la leyenda' in html),
                ("Layout completo", 'col-md-12' in html),
            ]
            
            print("\nResultados de verificación:")
            all_ok = True
            for name, passed in checks:
                status = "OK" if passed else "ERROR"
                print(f"  {name}: {status}")
                if not passed:
                    all_ok = False
            
            if all_ok:
                print("\n[SUCCESS] Todas las verificaciones pasaron.")
                print("La leyenda interactiva está implementada correctamente.")
                print("\nPara probar manualmente:")
                print("1. Visita http://127.0.0.1:8000/eventos/")
                print("2. Haz clic en los elementos de la leyenda para mostrar/ocultar líneas")
            else:
                print("\n[WARNING] Algunas verificaciones fallaron.")
                
        else:
            print(f"[ERROR] El servidor respondió con código {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("[ERROR] Timeout al conectar con el servidor")
        print("El servidor puede estar caído o respondiendo lentamente.")
    except requests.exceptions.ConnectionError:
        print("[ERROR] No se pudo conectar al servidor")
        print("Asegúrate de que el servidor Django esté ejecutándose en http://127.0.0.1:8000/")
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")

if __name__ == "__main__":
    test_simple()