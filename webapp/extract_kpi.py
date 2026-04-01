import requests
import re

url = 'http://127.0.0.1:8000/propifai/dashboard/calidad/'
response = requests.get(url)
html = response.text

# Buscar el div que contiene "Total Propiedades"
pattern = r'<div class="kpi-value">(\d+)</div>.*?Total Propiedades'
match = re.search(pattern, html, re.DOTALL)
if match:
    print('KPI Total Propiedades:', match.group(1))
else:
    # Buscar directamente el número después de kpi-value
    pattern2 = r'kpi-value[^>]*>(\d+)'
    matches = re.findall(pattern2, html)
    if matches:
        print('Todos los kpi-values:', matches)
    else:
        print('No encontrado')
        # Imprimir fragmento alrededor de Total Propiedades
        idx = html.find('Total Propiedades')
        if idx != -1:
            print(html[idx-200:idx+200])