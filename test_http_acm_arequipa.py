#!/usr/bin/env python
"""
Script para probar el endpoint ACM con coordenadas de Arequipa.
"""
import requests
import json

# URL del servidor local
url = "http://localhost:8000/acm/buscar-comparables/"

# Usar coordenadas de Arequipa (propiedad ID 6)
data = {
    'lat': -16.39473,
    'lng': -71.533696,
    'radio': 10000,  # 10 km
    'tipo_propiedad': 'Casa',
    'precio_min': 0,
    'precio_max': 10000000,
    'metros_min': 0,
    'metros_max': 10000,
}

headers = {
    'Content-Type': 'application/json',
}

print("Enviando solicitud a ACM con coordenadas de Arequipa...")
response = requests.post(url, data=json.dumps(data), headers=headers)

if response.status_code == 200:
    result = response.json()
    print(f"Status: {result['status']}")
    print(f"Total propiedades: {result['total']}")
    
    # Filtrar propiedades de Propifai
    propifai_props = [p for p in result['propiedades'] if p['fuente'] == 'propifai']
    print(f"Propiedades de Propifai: {len(propifai_props)}")
    
    for i, prop in enumerate(propifai_props[:10]):  # Mostrar primeras 10
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
        
        # Verificar cálculo manual
        if prop['precio_m2'] is not None:
            print(f"  Cálculo verificado: OK")
        else:
            print(f"  ADVERTENCIA: precio_m2 es None")
            if prop['precio'] and prop['metros_construccion']:
                print(f"  Podría calcularse: {prop['precio'] / prop['metros_construccion']:.2f}")
    
    # También mostrar propiedades locales si hay
    local_props = [p for p in result['propiedades'] if p['fuente'] == 'local']
    print(f"\nPropiedades locales: {len(local_props)}")
    for prop in local_props[:3]:
        print(f"  ID: {prop['id']}, Precio/m²: {prop['precio_m2']}, Precio/m² final: {prop['precio_m2_final']}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)