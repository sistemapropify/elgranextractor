#!/usr/bin/env python
import requests
import re

url = "http://localhost:8000/propifai/dashboard/visitas/"

print("Probando la inicialización simplificada...")
response = requests.get(url, timeout=10)
html = response.text

# Buscar mensajes de debug en el HTML
if 'debug-messages' in html:
    print("OK: Div de debug encontrado en la página")
    
    # Extraer el contenido del div de debug
    debug_pattern = r'<div[^>]*id="debug-messages"[^>]*>(.*?)</div>'
    debug_match = re.search(debug_pattern, html, re.DOTALL | re.IGNORECASE)
    if debug_match:
        debug_content = debug_match.group(1)
        # Extraer los mensajes de los párrafos
        msg_pattern = r'<p[^>]*>(.*?)</p>'
        messages = re.findall(msg_pattern, debug_content, re.DOTALL)
        print("\nMensajes de debug encontrados:")
        for msg in messages[:20]:  # Mostrar solo primeros 20
            print(f"  {msg}")
    else:
        print("ERROR: No se pudo extraer contenido del div de debug")
else:
    print("ERROR: Div de debug NO encontrado en la página")
    
# Buscar errores
if 'ERROR CRÍTICO' in html:
    print("\nADVERTENCIA: ERROR CRÍTICO encontrado en la página")
    # Extraer el error
    error_pattern = r'ERROR CRÍTICO:(.*?)<'
    error_match = re.search(error_pattern, html, re.DOTALL)
    if error_match:
        print(f"Error: {error_match.group(1).strip()}")
        
# Verificar si hay filas en la tabla
if '<tbody id="properties-tbody">' in html:
    tbody_start = html.find('<tbody id="properties-tbody">')
    tbody_end = html.find('</tbody>', tbody_start)
    if tbody_end > tbody_start:
        tbody_content = html[tbody_start:tbody_end+8]
        tr_count = tbody_content.count('<tr')
        print(f"\nFilas en la tabla: {tr_count}")
        
        if tr_count > 0:
            print("EXITO: ¡La tabla tiene filas! El dashboard está funcionando.")
            # Mostrar primera fila
            first_tr = re.search(r'<tr[^>]*>(.*?)</tr>', tbody_content, re.DOTALL)
            if first_tr:
                print(f"Primera fila: {first_tr.group(1)[:200]}...")
        else:
            print("ERROR: La tabla sigue vacía")
else:
    print("\nERROR: No se encontró tbody con id properties-tbody")

# Guardar un fragmento para inspección
with open('simplified_test.html', 'w', encoding='utf-8') as f:
    f.write(html[:10000])
print("\nFragmento guardado en simplified_test.html")