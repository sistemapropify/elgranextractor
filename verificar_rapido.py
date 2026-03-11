#!/usr/bin/env python
"""
Verificación rápida del HTML.
"""
import urllib.request
import re
import sys

print("=== VERIFICACIÓN RÁPIDA DEL HTML ===")
print()

url = 'http://localhost:8000/ingestas/propiedades/?fuente_propify=propify'

try:
    # Usar urllib con timeout corto
    req = urllib.request.Request(url)
    response = urllib.request.urlopen(req, timeout=5)
    html = response.read().decode('utf-8', errors='ignore')
    
    print(f"1. HTML obtenido: {len(html)} caracteres")
    
    # Buscar contador de Propify
    propify_pattern = r'propify.*?(\d+)'
    match = re.search(propify_pattern, html, re.IGNORECASE)
    if match:
        print(f"2. ✓ Contador de Propify encontrado: {match.group(0)}")
    else:
        print("2. ✗ NO se encontró contador de Propify")
        # Buscar en líneas específicas
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
    
    # Contar badges Propify
    badge_count = html.count('Propify</span>') + html.count('propify</span>')
    print(f"5. Total badges Propify: {badge_count}")
    
    # Buscar fragmento de ejemplo
    print("\n6. Fragmento de ejemplo:")
    start = html.find('<div class="property-card"')
    if start != -1:
        end = html.find('</div>', html.find('</div>', start) + 6) + 6
        if end > start:
            fragment = html[start:end]
            print(f"   Encontrado fragmento de {len(fragment)} caracteres")
            
            # Verificar si es Propify
            is_propify = 'data-es-propify="true"' in fragment
            has_badge = 'Propify</span>' in fragment or 'propify</span>' in fragment
            
            print(f"   Es Propify: {is_propify}")
            print(f"   Tiene badge Propify: {has_badge}")
            
            # Extraer tipo
            tipo_match = re.search(r'property-type.*?>(.*?)<', fragment, re.DOTALL)
            if tipo_match:
                print(f"   Tipo: {tipo_match.group(1).strip()[:50]}")
            
            # Mostrar primeras líneas
            lines = fragment.split('\n')
            for i in range(min(5, len(lines))):
                print(f"   {i}: {lines[i].strip()[:80]}")
    
    # Coordenadas
    print("\n7. Coordenadas:")
    lat_matches = re.findall(r'data-lat="([^"]+)"', html)
    lng_matches = re.findall(r'data-lng="([^"]+)"', html)
    
    print(f"   data-lat: {len(lat_matches)}")
    print(f"   data-lng: {len(lng_matches)}")
    
    # Filtrar vacías
    valid_lats = [lat for lat in lat_matches if lat and lat.strip()]
    valid_lngs = [lng for lng in lng_matches if lng and lng.strip()]
    
    print(f"   Válidas: {len(valid_lats)} lat, {len(valid_lngs)} lng")
    
    if valid_lats and valid_lngs:
        print(f"   Ejemplo: lat={valid_lats[0]}, lng={valid_lngs[0]}")
    
    # Verificar si hay texto "0 propify" en el HTML
    print("\n8. Verificación crítica:")
    if '0 propify' in html.lower():
        print("   ✗ CRÍTICO: HTML contiene '0 propify'")
        # Encontrar contexto
        idx = html.lower().find('0 propify')
        context = html[max(0, idx-100):min(len(html), idx+100)]
        print(f"   Contexto: ...{context}...")
    else:
        print("   ✓ HTML NO contiene '0 propify'")
        
    # Verificar conteo real
    if '43' in html and 'propify' in html.lower():
        print("   ✓ HTML contiene '43' junto con 'propify'")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== FIN DE VERIFICACIÓN ===")