#!/usr/bin/env python
"""
Simular la lógica del frontend para mostrar precio por m².
"""
import json

# Datos de ejemplo de la respuesta HTTP (tomados de la prueba anterior)
propiedades_ejemplo = [
    {
        'id': 51,
        'precio_m2': 1088.235294117647,
        'precio_m2_final': 1088.235294117647,
        'fuente': 'propifai'
    },
    {
        'id': 74,
        'precio_m2': None,
        'precio_m2_final': None,
        'fuente': 'propifai'
    },
    {
        'id': 2150,
        'precio_m2': 707.070707070707,
        'precio_m2_final': None,
        'fuente': 'local'
    }
]

print("Simulación de lógica frontend (acm.js línea 442):")
print("const precioM2 = propiedad.precio_m2_final || propiedad.precio_m2;")
print()

for prop in propiedades_ejemplo:
    precio_m2_final = prop['precio_m2_final']
    precio_m2 = prop['precio_m2']
    
    # Simular JavaScript: precio_m2_final || precio_m2
    # En JavaScript, null || valor => valor, undefined || valor => valor
    precioM2 = precio_m2_final if precio_m2_final is not None else precio_m2
    
    print(f"Propiedad {prop['id']} ({prop['fuente']}):")
    print(f"  precio_m2_final = {precio_m2_final}")
    print(f"  precio_m2 = {precio_m2}")
    print(f"  precioM2 (resultado) = {precioM2}")
    
    if precioM2:
        print(f"  Se mostraría: US$ {precioM2:.2f}/m²")
    else:
        print(f"  NO se mostraría (precioM2 es {precioM2})")
    print()