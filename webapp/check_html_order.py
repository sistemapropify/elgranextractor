import requests
from bs4 import BeautifulSoup

url = "http://127.0.0.1:8000/propifai/dashboard/calidad/"
response = requests.get(url)
if response.status_code != 200:
    print(f"Error: {response.status_code}")
    print(response.text[:500])
    exit()

html = response.text
soup = BeautifulSoup(html, 'html.parser')

# Encontrar la tabla con clase 'table-matrix'
table = soup.find('table', class_='table-matrix')
if not table:
    print("No se encontró la tabla")
    exit()

# Extraer todas las filas del tbody
tbody = table.find('tbody')
if not tbody:
    print("No se encontró tbody")
    exit()

rows = tbody.find_all('tr')
codes = []
for row in rows:
    # La primera columna (td) contiene el código
    first_td = row.find('td')
    if first_td:
        code = first_td.get_text(strip=True)
        codes.append(code)

print(f"Total propiedades en la tabla: {len(codes)}")
print("Primeras 10 propiedades:")
for i, code in enumerate(codes[:10]):
    print(f"{i}: {code}")

print("\nÚltimas 10 propiedades:")
for i, code in enumerate(codes[-10:]):
    print(f"{i+len(codes)-10}: {code}")

# Verificar orden
expected_first = "PROP000097"
expected_last = "PROP000001"  # asumiendo que la más antigua es la última

if codes and codes[0] == expected_first:
    print(f"\n¡ÉXITO! La primera propiedad es la más reciente ({expected_first}).")
else:
    print(f"\n¡PROBLEMA! La primera propiedad es {codes[0] if codes else 'N/A'}, se esperaba {expected_first}.")

if codes and codes[-1] == expected_last:
    print(f"¡ÉXITO! La última propiedad es la más antigua ({expected_last}).")
else:
    print(f"¡PROBLEMA! La última propiedad es {codes[-1] if codes else 'N/A'}, se esperaba {expected_last}.")