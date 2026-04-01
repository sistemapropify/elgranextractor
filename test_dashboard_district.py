#!/usr/bin/env python
"""
Test rápido para verificar que los nombres de distrito aparecen en el dashboard.
"""
import requests

try:
    resp = requests.get('http://127.0.0.1:8000/propifai/dashboard/calidad/', timeout=10)
    if resp.status_code == 200:
        print(f"Dashboard cargado (status {resp.status_code})")
        # Buscar algunas cadenas que indiquen nombres de distrito
        content = resp.text
        # Verificar que aparezca "Arequipa" o "Cerro Colorado" (nombres de distrito)
        if 'Arequipa' in content:
            print("✓ Distrito 'Arequipa' encontrado en la página")
        else:
            print("✗ Distrito 'Arequipa' NO encontrado")
        # Verificar que no aparezca el ID '1' como texto suelto (podría aparecer en otros contextos)
        # Pero mejor buscar una fila de tabla con district_name
        import re
        # Patrón para extraer celdas de distrito
        matches = re.findall(r'<td class="[^"]*">([^<]+)</td>', content)
        district_cells = [m for m in matches if m.strip() and m.strip() != '—']
        print(f"Celdas de distrito encontradas (primeras 5): {district_cells[:5]}")
        # Verificar que ninguna sea un número puro (como '1', '4')
        numeric = [c for c in district_cells if c.strip().isdigit()]
        if numeric:
            print(f"⚠️ Algunos distritos aún son números: {numeric[:3]}")
        else:
            print("✓ Todos los distritos parecen ser nombres (no números)")
    else:
        print(f"Error: status {resp.status_code}")
except Exception as e:
    print(f"Error al conectar: {e}")