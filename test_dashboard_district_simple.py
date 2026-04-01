#!/usr/bin/env python
"""
Test rápido para verificar que los nombres de distrito aparecen en el dashboard.
"""
import requests
import re

try:
    resp = requests.get('http://127.0.0.1:8000/propifai/dashboard/calidad/', timeout=10)
    if resp.status_code == 200:
        print(f"Dashboard cargado (status {resp.status_code})")
        content = resp.text
        # Verificar que aparezca "Arequipa" o "Cerro Colorado" (nombres de distrito)
        if 'Arequipa' in content:
            print("OK - Distrito 'Arequipa' encontrado en la página")
        else:
            print("WARNING - Distrito 'Arequipa' NO encontrado")
        # Verificar que no aparezca el ID '1' como texto suelto (podría aparecer en otros contextos)
        # Pero mejor buscar una fila de tabla con district_name
        # Patrón para extraer celdas de distrito
        matches = re.findall(r'<td class="[^"]*">([^<]+)</td>', content)
        district_cells = [m.strip() for m in matches if m.strip() and m.strip() != '—']
        print(f"Celdas de distrito encontradas (primeras 5): {district_cells[:5]}")
        # Verificar que ninguna sea un número puro (como '1', '4')
        numeric = [c for c in district_cells if c.isdigit()]
        if numeric:
            print(f"WARNING - Algunos distritos aún son números: {numeric[:3]}")
        else:
            print("OK - Todos los distritos parecen ser nombres (no números)")
        # Verificar también el panel de agregados por distrito
        if 'stats_por_distrito' in content:
            print("OK - Panel de agregados por distrito presente")
    else:
        print(f"Error: status {resp.status_code}")
except Exception as e:
    print(f"Error al conectar: {e}")