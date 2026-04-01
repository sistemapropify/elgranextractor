#!/usr/bin/env python
"""
Verificar el nuevo template.
"""
import requests
import re

def check_new_template():
    url = "http://localhost:8000/analisis-crm/"
    print(f"Haciendo solicitud a {url}")
    
    try:
        response = requests.get(url, timeout=5)
        print(f"Status code: {response.status_code}")
        
        # Buscar el script con los datos
        script_pattern = r'<script>.*?JSON\.parse\(\'(.*?)\'\).*?JSON\.parse\(\'(.*?)\'\)'
        match = re.search(script_pattern, response.text, re.DOTALL)
        
        if match:
            days_json = match.group(1)
            counts_json = match.group(2)
            print(f"\n=== DATOS ENCONTRADOS ===")
            print(f"days_of_month_json en template: '{days_json}'")
            print(f"counts_per_day_json en template: '{counts_json}'")
            
            # Verificar si están vacíos
            if days_json == '':
                print("¡ADVERTENCIA: days_of_month_json está vacío!")
            else:
                print(f"Longitud days_json: {len(days_json)}")
                
            if counts_json == '':
                print("¡ADVERTENCIA: counts_per_day_json está vacío!")
            else:
                print(f"Longitud counts_json: {len(counts_json)}")
                
            # Intentar parsear
            import json
            try:
                days = json.loads(days_json)
                counts = json.loads(counts_json)
                print(f"\n=== DATOS PARSEADOS ===")
                print(f"days: {days}")
                print(f"counts: {counts}")
                print(f"Número de días: {len(days)}")
                print(f"Número de conteos: {len(counts)}")
            except json.JSONDecodeError as e:
                print(f"\nERROR parseando JSON: {e}")
        else:
            print("\nNo se encontró el patrón de datos en el script")
            
        # Buscar también los valores crudos en el HTML
        print("\n=== BUSCANDO VALORES EN HTML ===")
        if 'days_of_month_json' in response.text:
            # Encontrar la línea
            lines = response.text.split('\n')
            for i, line in enumerate(lines):
                if 'days_of_month_json' in line:
                    print(f"Línea {i}: {line.strip()[:200]}...")
                    break
                    
        # Buscar el script completo para inspección
        script_section = re.search(r'<script>.*?</script>', response.text, re.DOTALL)
        if script_section:
            script_content = script_section.group(0)
            # Acortar para mostrar
            print(f"\n=== SCRIPT ENCONTRADO (primeras 500 chars) ===")
            print(script_content[:500])
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_new_template()