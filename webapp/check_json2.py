import requests
import re
import json

try:
    r = requests.get('http://localhost:8000/ingestas/propiedades/')
    print('Status:', r.status_code)
    print('Content length:', len(r.text))
    
    # Buscar el script con id todas-propiedades-data
    match = re.search(r'<script id="todas-propiedades-data" type="application/json">([^<]+)</script>', r.text)
    if match:
        json_str = match.group(1)
        print('JSON found, length:', len(json_str))
        print('First 200 chars:', json_str[:200])
        # Intentar cargar
        try:
            data = json.loads(json_str)
            print('Data type:', type(data))
            if isinstance(data, list):
                print('Total properties:', len(data))
                if len(data) > 0:
                    print('First item type:', type(data[0]))
                    print('First item keys:', data[0].keys() if isinstance(data[0], dict) else 'N/A')
                    # Contar Propify
                    propify = [p for p in data if isinstance(p, dict) and p.get('es_propify')]
                    print('Propify properties:', len(propify))
                    # Ver coordenadas
                    for i, p in enumerate(propify[:5]):
                        print(f"  {i}: ID: {p.get('id')}, lat: {p.get('lat')}, lng: {p.get('lng')}, tipo: {p.get('tipo_propiedad')}")
                    # Verificar iconos
                    print('Checking icon URLs...')
                    # Simular icon URL generation
                    import urllib.parse
                    icon_propify = '/static/requerimientos/data/Pin-propify.png'
                    print('Icon Propify path:', icon_propify)
            else:
                print('Data is not a list:', type(data))
                print('Data sample:', data[:200] if isinstance(data, str) else data)
        except json.JSONDecodeError as e:
            print('JSON decode error:', e)
            print('JSON snippet around error:', json_str[max(0, e.pos-50):e.pos+50])
    else:
        print('JSON script not found')
        # Buscar alternativa
        match2 = re.search(r'todas-propiedades-data[^>]*>([^<]+)', r.text)
        if match2:
            print('Alternative found:', match2.group(1)[:100])
except Exception as e:
    print('Error:', e)