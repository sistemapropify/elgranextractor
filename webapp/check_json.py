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
                    print('First item:', data[0])
                    # Contar Propify
                    propify = [p for p in data if isinstance(p, dict) and p.get('es_propify')]
                    print('Propify properties:', len(propify))
                    # Ver coordenadas
                    for p in propify[:3]:
                        print(f"  ID: {p.get('id')}, lat: {p.get('lat')}, lng: {p.get('lng')}")
            else:
                print('Data is not a list:', data)
        except json.JSONDecodeError as e:
            print('JSON decode error:', e)
    else:
        print('JSON script not found')
        # Buscar alternativa
        match2 = re.search(r'todas-propiedades-data[^>]*>([^<]+)', r.text)
        if match2:
            print('Alternative found:', match2.group(1)[:100])
except Exception as e:
    print('Error:', e)