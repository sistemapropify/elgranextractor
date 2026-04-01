import urllib.request
import re

url = 'http://localhost:8000/propifai/dashboard/visitas/'
html = urllib.request.urlopen(url).read().decode('utf-8')

# Buscar la tabla por su ID
match = re.search(r'<tbody id="properties-tbody">(.*?)</tbody>', html, re.DOTALL)
if match:
    tbody = match.group(1)
    # Contar filas <tr>
    rows = re.findall(r'<tr', tbody)
    print(f'Filas en tbody: {len(rows)}')
    if len(rows) == 0:
        print('El tbody está vacío. Posibles causas:')
        print('1. JavaScript no ha renderizado las filas (tal vez hay un error en el script)')
        print('2. Los filtros están ocultando todas las filas')
        print('3. El template no está generando las filas correctamente')
        # Imprimir el tbody para inspeccionar
        print('Contenido de tbody (primeros 500 caracteres):')
        print(tbody[:500])
    else:
        print('La tabla tiene filas. El dashboard debería mostrar datos.')
else:
    print('No se encontró el tbody con id properties-tbody')
    # Buscar cualquier tabla
    match = re.search(r'<table.*?class=".*?table-visits.*?".*?>(.*?)</table>', html, re.DOTALL)
    if match:
        print('Se encontró una tabla con clase table-visits')
        # Contar filas
        rows = re.findall(r'<tr', match.group(1))
        print(f'Filas totales en tabla: {len(rows)}')