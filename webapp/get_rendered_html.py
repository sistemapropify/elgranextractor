#!/usr/bin/env python
import requests
import re

url = "http://localhost:8000/propifai/dashboard/visitas/"

print("Obteniendo HTML renderizado...")
response = requests.get(url, timeout=10)
html = response.text

# Guardar el HTML completo
with open('rendered_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("HTML guardado en rendered_dashboard.html")

# Buscar la línea con propertiesData
lines = html.split('\n')
for i, line in enumerate(lines):
    if 'const propertiesData' in line:
        print(f"\nLínea {i+1}: {line.strip()}")
        
        # Verificar si la línea contiene {{ ... }}
        if '{{' in line and '}}' in line:
            print("¡ERROR! La variable template no fue renderizada")
            print("Esto significa que Django no está procesando el template correctamente")
        else:
            print("✓ La variable template fue renderizada")
            
        # Extraer el valor
        match = re.search(r'const propertiesData\s*=\s*(.*?);', line)
        if match:
            value = match.group(1)
            print(f"Valor: {value[:200]}...")
            
            # Verificar si es JSON válido
            import json
            try:
                data = json.loads(value)
                print(f"✓ JSON válido con {len(data)} elementos")
            except json.JSONDecodeError as e:
                print(f"✗ JSON inválido: {e}")
                print(f"  Valor problemático: {value[:100]}")
        break

# Buscar errores en la página
print("\nBuscando errores en la página...")
if 'Error JavaScript' in html:
    print("Se encontró 'Error JavaScript' en el HTML")
    # Extraer el div de error
    error_pattern = r'<div class="alert alert-danger">(.*?)</div>'
    error_match = re.search(error_pattern, html, re.DOTALL)
    if error_match:
        print("Contenido del error:")
        print(error_match.group(1)[:500])

# Verificar si Bootstrap está cargado
if 'bootstrap' in html.lower():
    print("✓ Bootstrap detectado en la página")
else:
    print("✗ Bootstrap NO detectado en la página")

# Verificar si hay scripts cargados
if '<script' in html:
    script_count = html.count('<script')
    print(f"✓ {script_count} scripts encontrados en la página")