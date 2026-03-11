import requests
import json

url = 'http://localhost:8000/ingestas/api/crear-propiedad/'

data = {
    "tipo_propiedad": "casa",
    "descripcion": "Casa de prueba desde API",
    "precio_usd": "150000",
    "lat": "-16.39889",
    "lng": "-71.535",
    "area_construida": "120",
    "numero_habitaciones": "3",
    "numero_banos": "2",
    "direccion": "Av. Ejemplo 123",
    "departamento": "Arequipa",
    "provincia": "Arequipa",
    "distrito": "Cayma",
    "area_terreno": "200",
    "numero_pisos": "2",
    "numero_cocheras": "1",
    "agente_inmobiliario": "Juan Perez",
    "imagenes_propiedad": "https://ejemplo.com/imagen.jpg",
    "id_propiedad": "TEST-001",
    "fecha_publicacion": "2026-03-02",
    "antiguedad": "5 años",
    "servicio_agua": True,
    "energia_electrica": True,
    "servicio_drenaje": True,
    "servicio_gas": False,
    "email_agente": "juan@example.com",
    "telefono_agente": "+51 999 999 999",
    "oficina_remax": "Remax Arequipa",
    "estado_propiedad": "en_publicacion",
    "fecha_venta": None,
    "precio_final_venta": None,
    "portal": "Manual"
}

headers = {
    'Content-Type': 'application/json',
}

try:
    response = requests.post(url, json=data, headers=headers)
    print(f'Status Code: {response.status_code}')
    print(f'Response: {response.json()}')
except Exception as e:
    print(f'Error: {e}')