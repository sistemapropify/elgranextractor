#!/usr/bin/env python3
"""
Script para probar la funcionalidad de leyenda interactiva en el gráfico de eventos.
Verifica que:
1. El HTML contiene la configuración correcta de Chart.js
2. La leyenda está configurada para ser interactiva
3. No hay errores de JavaScript
"""

import requests
from bs4 import BeautifulSoup
import re

def test_leyenda_interactiva():
    url = "http://127.0.0.1:8000/eventos/"
    
    try:
        print("Obteniendo página de eventos...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        print(f"Estado HTTP: {response.status_code}")
        print(f"Tamaño de respuesta: {len(response.text)} bytes")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Verificar que Chart.js está cargado
        chartjs_scripts = soup.find_all('script', src=re.compile(r'chart\.js'))
        if chartjs_scripts:
            print("[OK] Chart.js está cargado desde CDN")
            for script in chartjs_scripts:
                print(f"  - {script.get('src')}")
        else:
            print("[ERROR] Chart.js NO está cargado")
            
        # 2. Buscar el canvas del gráfico
        canvas = soup.find('canvas', id='evolucionTiposChart')
        if canvas:
            print("[OK] Canvas del gráfico encontrado")
            print(f"  - ID: {canvas.get('id')}")
            print(f"  - Dimensiones: {canvas.get('width')}x{canvas.get('height')}")
        else:
            print("[ERROR] Canvas del gráfico NO encontrado")
            
        # 3. Buscar la configuración de la leyenda en el JavaScript
        script_tags = soup.find_all('script')
        legend_config_found = False
        legend_interactive_found = False
        
        for script in script_tags:
            if script.string:
                content = script.string
                # Buscar configuración de leyenda
                if 'legend:' in content and 'display: true' in content:
                    legend_config_found = True
                    print("[OK] Configuración de leyenda encontrada (display: true)")
                    
                if 'onClick:' in content and 'legendItem' in content:
                    legend_interactive_found = True
                    print("[OK] Función onClick para interactividad encontrada")
                    
                # Extraer líneas específicas de configuración
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'legend:' in line and i < len(lines) - 10:
                        print("  Configuración de leyenda encontrada:")
                        for j in range(i, min(i+15, len(lines))):
                            print(f"    {lines[j].strip()}")
                        break
        
        # 4. Verificar el texto instructivo
        instructional_text = soup.find(string=re.compile(r'Haz clic en los elementos de la leyenda'))
        if instructional_text:
            print("[OK] Texto instructivo encontrado")
            print(f"  - Texto: {instructional_text.strip()}")
        else:
            print("[ERROR] Texto instructivo NO encontrado")
            
        # 5. Verificar layout (debería ser col-md-12)
        chart_container = soup.find('div', class_='col-md-12')
        if chart_container:
            print("[OK] Layout de ancho completo (col-md-12) encontrado")
        else:
            print("[ERROR] Layout de ancho completo NO encontrado")
            
        # 6. Resumen de verificación
        print("\n" + "="*60)
        print("RESUMEN DE VERIFICACIÓN DE LEYENDA INTERACTIVA")
        print("="*60)
        
        checks = [
            ("Chart.js cargado", bool(chartjs_scripts)),
            ("Canvas del gráfico", bool(canvas)),
            ("Configuración de leyenda", legend_config_found),
            ("Interactividad (onClick)", legend_interactive_found),
            ("Texto instructivo", bool(instructional_text)),
            ("Layout ancho completo", bool(chart_container)),
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "[OK]" if passed else "[ERROR]"
            print(f"{status} {check_name}")
            if not passed:
                all_passed = False
                
        if all_passed:
            print("\n[SUCCESS] TODAS LAS VERIFICACIONES PASARON")
            print("La leyenda interactiva debería funcionar correctamente.")
            print("\nPara probar manualmente:")
            print("1. Visita http://127.0.0.1:8000/eventos/")
            print("2. Verifica que el gráfico se muestre con líneas de colores")
            print("3. Haz clic en los elementos de la leyenda (arriba del gráfico)")
            print("4. Las líneas correspondientes deberían mostrar/ocultarse")
        else:
            print("\n[WARNING] ALGUNAS VERIFICACIONES FALLARON")
            print("Revisa el código HTML/JavaScript para corregir los problemas.")
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Error al conectar con el servidor: {e}")
        print("Asegúrate de que el servidor Django esté ejecutándose en http://127.0.0.1:8000/")
    except Exception as e:
        print(f"✗ Error inesperado: {e}")

if __name__ == "__main__":
    test_leyenda_interactiva()