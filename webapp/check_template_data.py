#!/usr/bin/env python
"""
Script para verificar qué datos están llegando al template.
"""
import requests
import re

def check_template_data():
    url = "http://localhost:8000/analisis-crm/"
    print(f"Haciendo solicitud a {url}")
    
    try:
        response = requests.get(url, timeout=5)
        print(f"Status code: {response.status_code}")
        
        # Buscar el div de debug
        debug_pattern = r'<div id="debug-data".*?>(.*?)</div>'
        match = re.search(debug_pattern, response.text, re.DOTALL)
        if match:
            debug_content = match.group(1)
            print("=== CONTENIDO DEBUG ===")
            print(debug_content)
        else:
            print("No se encontró el div debug-data")
            
        # Buscar los elementos script con los datos
        days_pattern = r'<script id="days-data".*?>(.*?)</script>'
        counts_pattern = r'<script id="counts-data".*?>(.*?)</script>'
        
        days_match = re.search(days_pattern, response.text, re.DOTALL)
        counts_match = re.search(counts_pattern, response.text, re.DOTALL)
        
        if days_match:
            days_content = days_match.group(1).strip()
            print(f"\n=== days-data content ===")
            print(f"Raw: '{days_content}'")
            print(f"Length: {len(days_content)}")
            if days_content == '""':
                print("¡ADVERTENCIA: days-data está vacío (cadena vacía)!")
            else:
                print(f"Contenido: {days_content[:100]}...")
        else:
            print("No se encontró days-data")
            
        if counts_match:
            counts_content = counts_match.group(1).strip()
            print(f"\n=== counts-data content ===")
            print(f"Raw: '{counts_content}'")
            print(f"Length: {len(counts_content)}")
            if counts_content == '""':
                print("¡ADVERTENCIA: counts-data está vacío (cadena vacía)!")
            else:
                print(f"Contenido: {counts_content[:100]}...")
        else:
            print("No se encontró counts-data")
            
        # Buscar también los valores directamente en el HTML
        print("\n=== BUSCANDO VALORES EN HTML ===")
        if 'days_of_month_json:' in response.text:
            # Encontrar la línea después de days_of_month_json:
            lines = response.text.split('\n')
            for i, line in enumerate(lines):
                if 'days_of_month_json:' in line:
                    print(f"Línea {i}: {line.strip()}")
                    # Mostrar las siguientes líneas también
                    for j in range(i, min(i+3, len(lines))):
                        print(f"  {lines[j].strip()}")
                    break
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_template_data()