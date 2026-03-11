import requests
import json

try:
    response = requests.get('http://localhost:8000/cuadrantizacion/zonas/')
    if response.status_code == 200:
        data = response.json()
        print(f'Total zonas: {len(data)}')
        for i, zone in enumerate(data):
            print(f'{i+1}. ID: {zone.get("id")}, Nombre: {zone.get("nombre_zona")}, Nivel: {zone.get("nivel")}, Padre: {zone.get("parent")}')
    else:
        print(f'Error: {response.status_code}')
        print(response.text[:500])
except Exception as e:
    print(f'Error: {e}')