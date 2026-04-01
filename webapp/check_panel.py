import requests
from bs4 import BeautifulSoup

url = 'http://127.0.0.1:8000/propifai/dashboard/calidad/'
resp = requests.get(url)
soup = BeautifulSoup(resp.text, 'html.parser')

# Encontrar el panel "Por Tipo" (buscar texto "Por Tipo")
panels = soup.find_all('div', class_='panel-card')
for panel in panels:
    header = panel.find('div', class_='panel-header')
    if header and 'Por Tipo' in header.get_text():
        print('Panel Por Tipo encontrado')
        table = panel.find('table', class_='panel-table')
        if table:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if cols:
                    print([col.get_text(strip=True) for col in cols])
        break