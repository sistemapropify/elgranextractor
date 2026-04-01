#!/usr/bin/env python
"""
Verificar si el script del gráfico está en el HTML.
"""
import requests
import re

def check_chart_script():
    url = "http://localhost:8000/analisis-crm/"
    print(f"Haciendo solicitud a {url}")
    
    try:
        response = requests.get(url, timeout=5)
        print(f"Status code: {response.status_code}")
        
        # Buscar el canvas del gráfico
        if 'id="leadsEvolutionChart"' in response.text:
            print("[OK] Canvas del gráfico encontrado")
        else:
            print("[ERROR] Canvas del gráfico NO encontrado")
            
        # Buscar el script de Chart.js
        if 'cdn.jsdelivr.net/npm/chart.js' in response.text:
            print("[OK] CDN de Chart.js encontrado")
        else:
            print("[ERROR] CDN de Chart.js NO encontrado")
            
        # Buscar el script con datos de ejemplo
        if 'Datos de ejemplo' in response.text:
            print("[OK] Texto 'Datos de ejemplo' encontrado")
        else:
            print("[ERROR] Texto 'Datos de ejemplo' NO encontrado")
            
        # Buscar el bloque extra_js
        if 'extra_js' in response.text:
            print("[OK] Bloque extra_js mencionado en HTML")
        else:
            print("[ERROR] Bloque extra_js no mencionado")
            
        # Extraer el script completo
        script_pattern = r'<script src="https://cdn\.jsdelivr\.net/npm/chart\.js"></script>.*?</script>'
        match = re.search(script_pattern, response.text, re.DOTALL)
        if match:
            print("\n[OK] Script del gráfico encontrado")
            script_content = match.group(0)
            # Mostrar primeras 300 caracteres
            print("Contenido del script (primeros 300 chars):")
            print(script_content[:300])
        else:
            print("\n[ERROR] Script del gráfico NO encontrado")
            # Buscar cualquier script después del canvas
            print("Buscando cualquier script...")
            all_scripts = re.findall(r'<script.*?</script>', response.text, re.DOTALL)
            print(f"Número total de scripts: {len(all_scripts)}")
            for i, script in enumerate(all_scripts[:3]):
                print(f"Script {i+1} (primeros 100 chars): {script[:100]}...")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_chart_script()