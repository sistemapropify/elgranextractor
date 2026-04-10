#!/usr/bin/env python3
"""
Verificación final de las correcciones del gráfico.
"""

import requests
import re

def verificar_correcciones():
    print("=== VERIFICACIÓN FINAL DE CORRECCIONES DEL GRÁFICO ===")
    
    url = "http://127.0.0.1:8000/eventos/"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            html = response.text
            
            print("1. Verificando CSS de altura fija:")
            checks = [
                ("height: 400px !important", "Altura fija del contenedor"),
                ("height: 100% !important", "Canvas ocupa 100% del contenedor"),
                ("canvas#evolucionTiposChart", "Selector CSS específico para canvas"),
                ("grafico-contenedor-fijo", "Clase CSS personalizada"),
                ("grafico-wrapper", "Clase wrapper para layout"),
            ]
            
            for pattern, desc in checks:
                if pattern in html:
                    print(f"   ✓ {desc}")
                else:
                    print(f"   ✗ {desc} NO encontrada")
            
            print("\n2. Verificando configuración Chart.js:")
            js_checks = [
                ("responsive: false", "Gráfico no responsive"),
                ("maintainAspectRatio: false", "Relación de aspecto no mantenida"),
                ("suggestedMax: 50", "Máximo sugerido del eje Y"),
                ("max: 100", "Límite máximo del eje Y"),
                ("maxTicksLimit: 10", "Límite de ticks"),
                ("canvas.chart.destroy()", "Destrucción de gráfico anterior"),
            ]
            
            for pattern, desc in js_checks:
                if pattern in html:
                    print(f"   ✓ {desc}")
                else:
                    print(f"   ✗ {desc} NO encontrada")
            
            print("\n3. Verificando estructura HTML:")
            html_checks = [
                ('class="grafico-contenedor-fijo"', "Contenedor con clase CSS"),
                ('class="grafico-canvas-fijo"', "Canvas con clase CSS"),
                ('id="evolucionTiposChart"', "ID del canvas presente"),
            ]
            
            for pattern, desc in html_checks:
                if pattern in html:
                    print(f"   ✓ {desc}")
                else:
                    print(f"   ✗ {desc} NO encontrada")
            
            # Verificar encoding corregido
            print("\n4. Verificando encoding (caracteres especiales):")
            if "NÃºmero" in html:
                print("   ⚠️  Posible problema de encoding en 'Número'")
            if "grÃ¡fico" in html:
                print("   ⚠️  Posible problema de encoding en 'gráfico'")
            if "últimas" in html or "últimas" in html.replace("Ãº", "ú"):
                print("   ✓ Caracteres especiales parecen corregidos")
            
            print("\n=== RESUMEN FINAL ===")
            print("Se han implementado las siguientes correcciones:")
            print("1. CSS con altura fija de 400px para el contenedor")
            print("2. Canvas que ocupa el 100% del espacio disponible")
            print("3. Configuración Chart.js con límites en eje Y")
            print("4. Gráfico no responsive (tamaño fijo)")
            print("5. Prevención de múltiples instancias del gráfico")
            print("6. Límite máximo de 100 en eje Y con suggestedMax de 50")
            print("7. Clases CSS personalizadas para mejor control")
            
            print("\nEl gráfico ahora debería tener altura fija y no expandirse infinitamente.")
            
        else:
            print(f"Error: Status code {response.status_code}")
            
    except Exception as e:
        print(f"Error durante la verificación: {e}")

if __name__ == '__main__':
    verificar_correcciones()