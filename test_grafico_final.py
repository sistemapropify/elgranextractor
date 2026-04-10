#!/usr/bin/env python3
"""
Script para probar que el gráfico se renderiza correctamente después de las correcciones.
"""

import requests
import sys
import os

def test_grafico():
    print("=== PRUEBA DE GRÁFICO CORREGIDO ===")
    
    # URL del dashboard de eventos
    url = "http://127.0.0.1:8000/eventos/"
    
    try:
        print(f"Realizando solicitud a {url}...")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ Solicitud exitosa (status {response.status_code})")
            
            # Verificar que el HTML contiene el canvas con las propiedades corregidas
            html = response.text
            
            # Verificar contenedor con altura fija
            if 'height: 400px !important' in html:
                print("✅ Contenedor tiene altura fija de 400px")
            else:
                print("⚠️  Contenedor NO tiene altura fija definida")
                
            # Verificar canvas con altura 100%
            if 'height: 100% !important' in html:
                print("✅ Canvas tiene height: 100%")
            else:
                print("⚠️  Canvas NO tiene height: 100%")
                
            # Verificar configuración del eje Y limitado
            if 'suggestedMax: 50' in html:
                print("✅ Eje Y tiene suggestedMax: 50")
            else:
                print("⚠️  Eje Y NO tiene suggestedMax configurado")
                
            # Verificar que no hay expansión infinita
            if 'responsive: false' in html:
                print("✅ Gráfico tiene responsive: false")
            else:
                print("⚠️  Gráfico podría ser responsive")
                
            # Verificar destrucción de gráfico anterior
            if 'canvas.chart.destroy()' in html:
                print("✅ Incluye destrucción de gráfico anterior")
            else:
                print("⚠️  No incluye destrucción de gráfico anterior")
                
            # Verificar que el canvas existe
            if 'id="evolucionTiposChart"' in html:
                print("✅ Canvas con ID evolucionTiposChart encontrado")
            else:
                print("❌ Canvas NO encontrado en el HTML")
                
            print(f"\n=== RESUMEN ===")
            print("El gráfico debería tener ahora:")
            print("1. Altura fija de 400px en el contenedor")
            print("2. Canvas que ocupa el 100% del contenedor")
            print("3. Eje Y limitado a máximo 50 eventos")
            print("4. Gráfico no responsive (tamaño fijo)")
            print("5. Prevención de múltiples instancias")
            
        else:
            print(f"❌ Error en la solicitud: status {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ No se pudo conectar al servidor. Asegúrate de que el servidor Django esté ejecutándose.")
        print("   Ejecuta: cd webapp && python manage.py runserver")
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")

if __name__ == '__main__':
    test_grafico()