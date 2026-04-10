#!/usr/bin/env python3
"""
Script simple para probar que el gráfico se renderiza correctamente.
"""

import requests
import sys

def test_grafico():
    print("=== PRUEBA DE GRAFICO CORREGIDO ===")
    
    # URL del dashboard de eventos
    url = "http://127.0.0.1:8000/eventos/"
    
    try:
        print(f"Realizando solicitud a {url}...")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print(f"OK - Solicitud exitosa (status {response.status_code})")
            
            # Verificar que el HTML contiene el canvas con las propiedades corregidas
            html = response.text
            
            # Verificar contenedor con altura fija
            if 'height: 400px !important' in html:
                print("OK - Contenedor tiene altura fija de 400px")
            else:
                print("ADVERTENCIA - Contenedor NO tiene altura fija definida")
                
            # Verificar canvas con altura 100%
            if 'height: 100% !important' in html:
                print("OK - Canvas tiene height: 100%")
            else:
                print("ADVERTENCIA - Canvas NO tiene height: 100%")
                
            # Verificar configuración del eje Y limitado
            if 'suggestedMax: 50' in html:
                print("OK - Eje Y tiene suggestedMax: 50")
            else:
                print("ADVERTENCIA - Eje Y NO tiene suggestedMax configurado")
                
            # Verificar que no hay expansión infinita
            if 'responsive: false' in html:
                print("OK - Grafico tiene responsive: false")
            else:
                print("ADVERTENCIA - Grafico podria ser responsive")
                
            # Verificar destrucción de gráfico anterior
            if 'canvas.chart.destroy()' in html:
                print("OK - Incluye destruccion de grafico anterior")
            else:
                print("ADVERTENCIA - No incluye destruccion de grafico anterior")
                
            # Verificar que el canvas existe
            if 'id="evolucionTiposChart"' in html:
                print("OK - Canvas con ID evolucionTiposChart encontrado")
            else:
                print("ERROR - Canvas NO encontrado en el HTML")
                
            print(f"\n=== RESUMEN ===")
            print("El grafico deberia tener ahora:")
            print("1. Altura fija de 400px en el contenedor")
            print("2. Canvas que ocupa el 100% del contenedor")
            print("3. Eje Y limitado a maximo 50 eventos")
            print("4. Grafico no responsive (tamano fijo)")
            print("5. Prevencion de multiples instancias")
            
            # Verificar tamaño aproximado del HTML
            print(f"\nTamano del HTML: {len(html)} caracteres")
            
        else:
            print(f"ERROR - Error en la solicitud: status {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("ERROR - No se pudo conectar al servidor.")
        print("   Asegurate de que el servidor Django este ejecutandose.")
    except Exception as e:
        print(f"ERROR - Error durante la prueba: {e}")

if __name__ == '__main__':
    test_grafico()