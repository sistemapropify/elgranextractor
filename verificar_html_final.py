#!/usr/bin/env python
"""
Verificación final del HTML generado para Propify.
"""
import requests
import re

print("=== VERIFICACIÓN HTML FINAL ===")
print()

# Hacer una solicitud HTTP real al servidor local
url = 'http://localhost:8000/ingestas/propiedades/?fuente_propify=propify'
try:
    print(f"1. Solicitando URL: {url}")
    response = requests.get(url, timeout=10)
    print(f"   Status: {response.status_code}")
    print(f"   Content length: {len(response.text)} caracteres")
    
    html = response.text
    
    print("\n2. Buscando contadores en el HTML:")
    
    # Buscar el contador de Propify específicamente en el HTML
    # El contador debería estar en algo como: <span class="badge">propify: 43</span>
    propify_patterns = [
        r'propify.*?(\d+)',
        r'Propify.*?(\d+)',
        r'fuente.*?propify.*?(\d+)',
        r'conteo.*?propify.*?(\d+)'
    ]
    
    found_count = False
    for pattern in propify_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            print(f"   ✓ Encontrado patrón '{pattern}': {matches}")
            found_count = True
            break
    
    if not found_count:
        print("   ✗ No se encontró el contador de Propify en el HTML")
        
    # Buscar el texto exacto del contador en el HTML
    print("\n3. Buscando texto específico del contador:")
    lines = html.split('\n')
    for i, line in enumerate(lines):
        if 'propify' in line.lower() and ('0' in line or '43' in line or 'conteo' in line.lower() or 'fuente' in line.lower()):
            print(f"   Línea {i}: {line.strip()[:150]}")
    
    print("\n4. Verificando propiedades en el HTML:")
    
    # Contar property-card
    property_card_count = html.count('property-card')
    print(f"   Total 'property-card' encontrados: {property_card_count}")
    
    # Verificar si hay propiedades Propify en las cards
    propify_in_cards = html.count('data-es-propify="true"')
    print(f"   Total 'data-es-propify=\"true\"' encontrados: {propify_in_cards}")
    
    # Verificar si hay el badge "Propify" en las cards
    propify_badge_count = html.count('Propify</span>') + html.count('propify</span>')
    print(f"   Total badges 'Propify' encontrados: {propify_badge_count}")
    
    print("\n5. Extracción de fragmento HTML con propiedades:")
    
    # Encontrar la sección de propiedades
    if '<div class="properties-container"' in html:
        start = html.find('<div class="properties-container"')
        end = html.find('</div>', start + 1000) + 6
        if end > start:
            fragment = html[start:end]
            # Contar property-card en el fragmento
            fragment_card_count = fragment.count('property-card')
            print(f"   Fragmento properties-container encontrado")
            print(f"   Property-card en fragmento: {fragment_card_count}")
            
            # Mostrar primeras 2 cards
            card_start = 0
            for i in range(2):
                card_start = fragment.find('<div class="property-card"', card_start)
                if card_start == -1:
                    break
                card_end = fragment.find('</div>', fragment.find('</div>', card_start) + 6) + 6
                if card_end > card_start:
                    card = fragment[card_start:card_end]
                    # Verificar si es Propify
                    is_propify = 'data-es-propify="true"' in card
                    has_propify_badge = 'Propify</span>' in card or 'propify</span>' in card
                    print(f"\n   Card {i+1}:")
                    print(f"     Es Propify: {is_propify}")
                    print(f"     Tiene badge Propify: {has_propify_badge}")
                    # Extraer tipo de propiedad
                    tipo_match = re.search(r'property-type.*?>(.*?)<', card, re.DOTALL)
                    if tipo_match:
                        print(f"     Tipo: {tipo_match.group(1).strip()[:50]}")
                    card_start = card_end
    
    print("\n6. Verificación de mapa (coordenadas):")
    
    # Buscar coordenadas en el HTML
    lat_pattern = r'data-lat="([^"]+)"'
    lng_pattern = r'data-lng="([^"]+)"'
    
    lat_matches = re.findall(lat_pattern, html)
    lng_matches = re.findall(lng_pattern, html)
    
    print(f"   Coordenadas data-lat encontradas: {len(lat_matches)}")
    print(f"   Coordenadas data-lng encontradas: {len(lng_matches)}")
    
    # Filtrar coordenadas no vacías
    valid_lats = [lat for lat in lat_matches if lat and lat.strip()]
    valid_lngs = [lng for lng in lng_matches if lng and lng.strip()]
    
    print(f"   Coordenadas válidas (no vacías): {len(valid_lats)} lat, {len(valid_lngs)} lng")
    
    if valid_lats and valid_lngs:
        print(f"   Primeras coordenadas: lat={valid_lats[0]}, lng={valid_lngs[0]}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== VERIFICACIÓN COMPLETADA ===")