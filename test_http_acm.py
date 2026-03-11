#!/usr/bin/env python
"""
Script para probar el endpoint ACM directamente via HTTP.
"""
import requests
import json

# URL del servidor local
url = "http://localhost:8000/acm/buscar-comparables/"

# Datos de prueba con radio grande para capturar propiedades
data = {
    'lat': -12.0464,  # Lima centro
    'lng': -77.0428,
    'radio': 50000,  # 50 km (radio grande para capturar propiedades)
    'tipo_propiedad': 'Casa',
    'precio_min': 0,
    'precio_max': 10000000,
    'metros_min': 0,
    'metros_max': 10000,
}

headers = {
    'Content-Type': 'application/json',
    'X-CSRFToken': 'test',  # No necesario porque la vista tiene @csrf_exempt
}

print("Enviando solicitud a ACM...")
response = requests.post(url, data=json.dumps(data), headers=headers)

if response.status_code == 200:
    result = response.json()
    print(f"Status: {result['status']}")
    print(f"Total propiedades: {result['total']}")
    
    # Filtrar propiedades de Propifai
    propifai_props = [p for p in result['propiedades'] if p['fuente'] == 'propifai']
    print(f"Propiedades de Propifai: {len(propifai_props)}")
    
    for i, prop in enumerate(propifai_props[:5]):  # Mostrar primeras 5
        print(f"\n--- Propiedad Propifai {i+1} ---")
        print(f"ID: {prop['id']}")
        print(f"Tipo: {prop['tipo']}")
        print(f"Precio: {prop['precio']}")
        print(f"Área construida: {prop['metros_construccion']}")
        print(f"Área terreno: {prop['metros_terreno']}")
        print(f"Precio/m²: {prop['precio_m2']}")
        print(f"Precio/m² final: {prop['precio_m2_final']}")
        print(f"¿Tiene precio_m2? {prop['precio_m2'] is not None}")
        print(f"¿Tiene precio_m2_final? {prop['precio_m2_final'] is not None}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)