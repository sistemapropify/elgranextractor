import requests
import sys

url = 'http://127.0.0.1:8000/propifai/dashboard/calidad/'
try:
    resp = requests.get(url)
    print('Status:', resp.status_code)
    # Extraer algunos números del HTML
    import re
    # Buscar KPIs
    matches = re.findall(r'kpi-value[^>]*>([^<]+)', resp.text)
    if matches:
        print('KPIs:', matches)
    else:
        print('No se encontraron KPIs')
except Exception as e:
    print('Error:', e)
    sys.exit(1)