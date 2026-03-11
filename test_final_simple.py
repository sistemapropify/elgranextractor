#!/usr/bin/env python
"""
Test final simple para verificar si las propiedades Propify se muestran.
"""
import urllib.request
import re

print("=== TEST FINAL SIMPLE ===")
print()

url = 'http://localhost:8000/ingestas/propiedades/?fuente_propify=propify'

try:
    # Hacer la solicitud
    req = urllib.request.Request(url)
    response = urllib.request.urlopen(req, timeout=15)
    html = response.read().decode('utf-8', errors='ignore')
    
    print(f"1. HTML obtenido: {len(html)} caracteres")
    
    # Buscar contador de Propify
    propify_pattern = r'propify.*?(\d+)'
    match = re.search(propify_pattern, html, re.IGNORECASE)
    
    if match:
        print(f"2. ✓ Contador de Propify encontrado: {match.group(0)}")
    else:
        print("2. ✗ NO se encontró contador de Propify")
        # Buscar en el HTML la línea con el contador
        lines = html.split('\n')
        for i, line in enumerate(lines):
            if 'propify' in line.lower():
                print(f"   Línea {i}: {line.strip()[:100]}")
    
    # Contar property-card
    card_count = html.count('property-card')
    print(f"3. Total property-card: {card_count}")
    
    # Contar data-es-propify
    propify_count = html.count('data-es-propify="true"')
    print(f"4. Total data-es-propify=\"true\": {propify_count}")
    
    # Verificar si hay coordenadas
    lat_count = len(re.findall(r'data-lat="([^"]+)"', html))
    lng_count = len(re.findall(r'data-lng="([^"]+)"', html))
    print(f"5. Coordenadas: {lat_count} lat, {lng_count} lng")
    
    # Verificar si el HTML contiene "0 propify"
    if '0 propify' in html.lower():
        print("6. ✗ CRÍTICO: HTML contiene '0 propify'")
    else:
        print("6. ✓ HTML NO contiene '0 propify'")
    
    # Extraer un fragmento para ver
    print("\n7. Fragmento del HTML (primeros 500 caracteres después de 'property-card'):")
    start = html.find('property-card')
    if start != -1:
        fragment = html[start:start+500]
        print(fragment)
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== TEST COMPLETADO ===")