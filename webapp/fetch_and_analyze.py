#!/usr/bin/env python
import requests
import re
import json

url = "http://localhost:8000/propifai/dashboard/visitas/"

try:
    print("Obteniendo página del dashboard...")
    response = requests.get(url, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    
    html = response.text
    
    # Buscar el título
    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if title_match:
        print(f"Título: {title_match.group(1)}")
    
    # Buscar properties-tbody
    if 'id="properties-tbody"' in html:
        print("OK: Elemento properties-tbody encontrado")
    else:
        print("ERROR: Elemento properties-tbody NO encontrado")
        # Buscar alternativas
        if 'id="properties-table-body"' in html:
            print("  (pero encontré properties-table-body)")
    
    # Buscar el script con propertiesData
    # Patrón 1: const propertiesData = JSON.parse('...');
    pattern1 = r'const propertiesData\s*=\s*JSON\.parse\(\s*["\'](.*?)["\']\s*\)'
    # Patrón 2: const propertiesData = [...];
    pattern2 = r'const propertiesData\s*=\s*(\[.*?\])\s*;'
    # Patrón 3: var propertiesData = {{ properties_json|safe }};
    pattern3 = r'const propertiesData\s*=\s*(.*?);'
    
    match = None
    json_str = None
    
    # Intentar patrón 1 primero
    match = re.search(pattern1, html, re.DOTALL)
    if match:
        print("OK: Encontrado propertiesData con JSON.parse()")
        json_str = match.group(1)
        # Decodificar escapes JSON
        json_str = json_str.replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\')
    else:
        # Intentar patrón 2
        match = re.search(pattern2, html, re.DOTALL)
        if match:
            print("OK: Encontrado propertiesData como array literal")
            json_str = match.group(1)
        else:
            # Intentar patrón 3 (template variable)
            match = re.search(pattern3, html, re.DOTALL)
            if match:
                print("OK: Encontrado propertiesData (posiblemente variable template)")
                json_str = match.group(1)
    
    if json_str:
        print(f"\nJSON encontrado (primeros 300 caracteres):")
        print(json_str[:300] + ("..." if len(json_str) > 300 else ""))
        
        # Intentar parsear
        try:
            if json_str.startswith('{{') and '}}' in json_str:
                print("ERROR: Parece ser una variable template no renderizada: " + json_str[:100])
            else:
                data = json.loads(json_str)
                print(f"OK: JSON parseado correctamente")
                print(f"  Tipo: {type(data)}")
                if isinstance(data, list):
                    print(f"  Número de propiedades: {len(data)}")
                    if len(data) > 0:
                        print(f"  Primera propiedad:")
                        print(f"    ID: {data[0].get('id')}")
                        print(f"    Código: {data[0].get('code')}")
                        print(f"    Título: {data[0].get('title')}")
                        print(f"    Total eventos: {data[0].get('total_eventos')}")
                        print(f"    Status: {data[0].get('status')}")
                    else:
                        print("  ADVERTENCIA: La lista de propiedades está vacía")
                else:
                    print(f"  Contenido: {json.dumps(data, indent=2)[:200]}...")
        except json.JSONDecodeError as e:
            print(f"ERROR parseando JSON: {e}")
            print(f"  JSON problemático: {json_str[:200]}")
    else:
        print("\nERROR: No se pudo encontrar propertiesData en el HTML")
        
        # Buscar properties_json en el HTML
        if 'properties_json' in html:
            print("  (pero 'properties_json' aparece en el código)")
            
            # Extraer línea con properties_json
            lines = html.split('\n')
            for i, line in enumerate(lines):
                if 'properties_json' in line:
                    print(f"  Línea {i+1}: {line.strip()[:100]}")
    
    # Buscar errores JavaScript
    if 'console.error' in html:
        print("\nADVERTENCIA: Se encontraron console.error en el código JavaScript")
        # Extraer líneas con console.error
        lines = html.split('\n')
        error_lines = [i+1 for i, line in enumerate(lines) if 'console.error' in line]
        print(f"  Líneas con console.error: {error_lines[:5]}")
    
    # Verificar si hay datos en la tabla
    if '<tbody id="properties-tbody">' in html:
        tbody_start = html.find('<tbody id="properties-tbody">')
        tbody_end = html.find('</tbody>', tbody_start)
        if tbody_end > tbody_start:
            tbody_content = html[tbody_start:tbody_end+8]
            # Contar filas <tr> dentro del tbody
            tr_count = tbody_content.count('<tr')
            print(f"\nTabla tbody contiene {tr_count} filas <tr>")
            if tr_count == 0:
                print("  ADVERTENCIA: El tbody está vacío (sin filas)")
    
    # Guardar fragmento para inspección
    with open('dashboard_fragment.html', 'w', encoding='utf-8') as f:
        f.write(html[:5000])
    print("\nFragmento de HTML guardado en dashboard_fragment.html")
    
except requests.exceptions.ConnectionError:
    print("ERROR: No se pudo conectar al servidor. ¿Está corriendo Django?")
    print("  Ejecuta: cd webapp && py manage.py runserver")
except Exception as e:
    print(f"ERROR: {e}")