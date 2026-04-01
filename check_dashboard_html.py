#!/usr/bin/env python
"""
Script para verificar el HTML del dashboard y extraer algunas filas de la tabla.
"""
import requests

url = 'http://127.0.0.1:8000/propifai/dashboard/calidad/'
try:
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        html = response.text
        # Encontrar la tabla de matriz
        start = html.find('<table class="table table-matrix')
        if start == -1:
            print("Tabla no encontrada en el HTML")
            # Buscar cualquier tabla
            start = html.find('<tbody>')
            if start == -1:
                print("No se encontró tbody")
                exit(1)
            start = html.rfind('<table', 0, start)
        
        end = html.find('</table>', start)
        if end == -1:
            print("No se encontró cierre de tabla")
            exit(1)
        
        table_html = html[start:end+8]
        # Extraer las primeras 5 filas del tbody
        tbody_start = table_html.find('<tbody>')
        tbody_end = table_html.find('</tbody>')
        if tbody_start != -1 and tbody_end != -1:
            tbody = table_html[tbody_start:tbody_end+8]
            # Dividir por filas <tr>
            rows = tbody.split('<tr')
            # Mostrar las primeras 5 filas (excluyendo el primer elemento que puede ser vacío)
            for i, row in enumerate(rows[1:6]):
                print(f"\n--- Fila {i+1} ---")
                # Extraer celdas <td>
                cells = row.split('<td')
                for j, cell in enumerate(cells[1:]):  # saltar el primer fragmento antes del primer <td
                    # Encontrar el contenido de la celda
                    content_start = cell.find('>')
                    content_end = cell.find('</td>')
                    if content_start != -1 and content_end != -1:
                        content = cell[content_start+1:content_end].strip()
                        # Limpiar etiquetas HTML
                        import re
                        content = re.sub(r'<[^>]+>', '', content)
                        content = re.sub(r'\s+', ' ', content)
                        if j == 3:  # columna de tipo de propiedad (índice 3, considerando que la primera columna es 0?)
                            print(f"  Columna {j}: {content[:100]}")
                        else:
                            if j < 5:  # solo mostrar primeras columnas
                                print(f"  Columna {j}: {content[:50]}")
        else:
            print("No se encontró tbody en la tabla")
        
        # También buscar la palabra "Casa" o "Departamento" en el HTML para verificar que aparezcan
        if 'Casa' in html:
            print("\n✅ La palabra 'Casa' aparece en el HTML")
        if 'Departamento' in html:
            print("✅ La palabra 'Departamento' aparece en el HTML")
        if 'Terreno' in html:
            print("✅ La palabra 'Terreno' aparece en el HTML")
        if 'Propiedad' in html:
            print("⚠️  La palabra 'Propiedad' aparece en el HTML (puede ser residual)")
    else:
        print(f"Error: status code {response.status_code}")
except Exception as e:
    print(f"Error al obtener el dashboard: {e}")