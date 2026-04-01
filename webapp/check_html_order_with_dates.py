import requests
from bs4 import BeautifulSoup
from datetime import datetime

url = "http://127.0.0.1:8000/propifai/dashboard/calidad/"
response = requests.get(url)
if response.status_code != 200:
    print(f"Error: {response.status_code}")
    exit()

html = response.text
soup = BeautifulSoup(html, 'html.parser')

table = soup.find('table', class_='table-matrix')
if not table:
    print("No se encontró la tabla")
    exit()

tbody = table.find('tbody')
if not tbody:
    print("No se encontró tbody")
    exit()

rows = tbody.find_all('tr')
data = []
for row in rows:
    tds = row.find_all('td')
    if len(tds) >= 14:  # Necesitamos al menos 14 columnas
        code = tds[0].get_text(strip=True)
        date_str = tds[12].get_text(strip=True)  # Fecha de creación (columna 13, índice 12)
        data.append((code, date_str))

print(f"Total propiedades en la tabla: {len(data)}")
print("Primeras 5 propiedades con fecha:")
for i, (code, date_str) in enumerate(data[:5]):
    print(f"{i}: {code} - {date_str}")

print("\nÚltimas 5 propiedades con fecha:")
for i, (code, date_str) in enumerate(data[-5:]):
    print(f"{i+len(data)-5}: {code} - {date_str}")

# Intentar parsear fechas (formato d/m/Y)
parsed_dates = []
for code, date_str in data:
    if date_str and date_str != '—':
        try:
            dt = datetime.strptime(date_str, '%d/%m/%Y')
            parsed_dates.append(dt)
        except ValueError:
            parsed_dates.append(None)
    else:
        parsed_dates.append(None)

# Verificar si las fechas están en orden descendente (más reciente primero)
valid_dates = [(i, dt) for i, dt in enumerate(parsed_dates) if dt is not None]
if len(valid_dates) > 1:
    is_descending = all(valid_dates[i][1] >= valid_dates[i+1][1] for i in range(len(valid_dates)-1))
    if is_descending:
        print("\n¡Las fechas están en orden descendente (más recientes primero)!")
    else:
        print("\n¡Las fechas NO están en orden descendente!")
        # Mostrar pares problemáticos
        for i in range(len(valid_dates)-1):
            if valid_dates[i][1] < valid_dates[i+1][1]:
                print(f"  Problema en índice {valid_dates[i][0]}: {valid_dates[i][1].date()} < {valid_dates[i+1][1].date()}")
else:
    print("\nNo hay suficientes fechas para verificar el orden.")