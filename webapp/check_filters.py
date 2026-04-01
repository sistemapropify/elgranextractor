import requests
from bs4 import BeautifulSoup

url = 'http://127.0.0.1:8000/propifai/dashboard/calidad/'
resp = requests.get(url)
soup = BeautifulSoup(resp.text, 'html.parser')

# Obtener botones de filtro
filter_buttons = soup.select('.filter-buttons button[data-filter]')
print('Botones de filtro:')
for btn in filter_buttons:
    print(f"  {btn.get_text(strip=True)} -> data-filter='{btn.get('data-filter')}'")

# Obtener todos los rows de la tabla
rows = soup.select('.table-matrix tbody tr')
print(f'\nTotal filas: {len(rows)}')
status_counts = {}
for row in rows:
    status = row.get('data-status')
    if status is None:
        status = '(vacío)'
    status_counts[status] = status_counts.get(status, 0) + 1

print('\nConteo de status (todas las filas):')
for status, count in sorted(status_counts.items()):
    print(f"  '{status}': {count}")

# Verificar que cada status tenga un botón correspondiente
filters = [btn.get('data-filter') for btn in filter_buttons]
print('\nVerificación de correspondencia:')
for status in status_counts.keys():
    if status not in filters and status != 'all' and status != '(vacío)':
        print(f"  ADVERTENCIA: status '{status}' no tiene botón correspondiente")

# Mostrar algunos ejemplos de filas sin status
empty_rows = [i for i, row in enumerate(rows) if row.get('data-status') is None]
if empty_rows:
    print(f'\nFilas sin data-status (índices): {empty_rows[:5]}')
    # Inspeccionar una fila sin status
    idx = empty_rows[0]
    row = rows[idx]
    print(f'  Ejemplo fila {idx}:')
    cols = row.select('td')
    if cols:
        print(f'    Primera celda: {cols[0].get_text(strip=True)[:50]}')