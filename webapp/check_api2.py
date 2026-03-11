import requests
import json

try:
    response = requests.get('http://localhost:8000/cuadrantizacion/zonas/')
    print(f'Status: {response.status_code}')
    print(f'Content-Type: {response.headers.get("content-type")}')
    print('First 500 chars:')
    print(response.text[:500])
    if response.status_code == 200:
        try:
            data = response.json()
            print(f'JSON parsed, type: {type(data)}')
            if isinstance(data, list):
                print(f'Total zonas: {len(data)}')
                for i, zone in enumerate(data):
                    print(f'{i+1}. {zone}')
            else:
                print(f'Data is not a list: {data}')
        except json.JSONDecodeError as e:
            print(f'JSON decode error: {e}')
except Exception as e:
    print(f'Error: {e}')