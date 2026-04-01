#!/usr/bin/env python
import requests

url = "http://localhost:8000/propifai/dashboard/visitas/"

print("Obteniendo HTML completo...")
response = requests.get(url, timeout=10)
html = response.text

# Guardar el HTML completo
with open('full_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f"HTML guardado en full_dashboard.html ({len(html)} caracteres)")

# Buscar el script
if '<script>' in html:
    # Encontrar el último script (nuestro código)
    scripts = html.split('<script>')
    last_script = scripts[-1].split('</script>')[0] if '</script>' in scripts[-1] else scripts[-1]
    
    print("\n=== ÚLTIMO SCRIPT ENCONTRADO (primeras 2000 chars) ===")
    print(last_script[:2000])
    
    # Buscar errores
    if 'error' in last_script.lower():
        print("\n=== POSIBLES ERRORES EN SCRIPT ===")
        lines = last_script.split('\n')
        for i, line in enumerate(lines):
            if 'error' in line.lower():
                print(f"Línea {i}: {line.strip()[:100]}")

# Buscar el tbody
if 'properties-tbody' in html:
    print("\n=== TBODY ENCONTRADO ===")
    tbody_start = html.find('id="properties-tbody"')
    if tbody_start != -1:
        # Encontrar el tbody completo
        tbody_tag_start = html.rfind('<tbody', 0, tbody_start)
        tbody_tag_end = html.find('</tbody>', tbody_start)
        if tbody_tag_end > tbody_tag_start:
            tbody_content = html[tbody_tag_start:tbody_tag_end+8]
            print(f"Contenido del tbody ({len(tbody_content)} caracteres):")
            print(tbody_content[:500])
            
            # Contar filas
            tr_count = tbody_content.count('<tr')
            print(f"\nNúmero de filas <tr> en tbody: {tr_count}")