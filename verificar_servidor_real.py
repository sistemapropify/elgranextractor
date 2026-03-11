#!/usr/bin/env python
"""
Verificar el servidor real accediendo a la URL local.
"""
import requests
import re

print("=== VERIFICACIÓN DEL SERVIDOR REAL ===")
print()

# URLs a probar
urls = [
    ("Sin filtros", "http://localhost:8000/ingestas/propiedades/"),
    ("Solo Propify", "http://localhost:8000/ingestas/propiedades/?fuente_propify=propify"),
    ("Solo locales", "http://localhost:8000/ingestas/propiedades/?fuente_local=local"),
    ("Solo externas", "http://localhost:8000/ingestas/propiedades/?fuente_externa=externa"),
]

for name, url in urls:
    print(f"Probando: {name}")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            
            # Buscar contadores
            conteo_match = re.search(r'(\d+)\s*propify', content, re.IGNORECASE)
            if conteo_match:
                print(f"  Contador propify encontrado: {conteo_match.group(1)}")
            else:
                print(f"  Contador propify NO encontrado")
                
            # Buscar tarjetas Propify
            propify_cards = len(re.findall(r'data-es-propify="true"', content))
            print(f"  Tarjetas con data-es-propify='true': {propify_cards}")
            
            # Buscar texto "Propify" en las tarjetas
            propify_text = len(re.findall(r'Propify', content, re.IGNORECASE))
            print(f"  Texto 'Propify' aparece {propify_text} veces")
            
            # Total de tarjetas
            total_cards = len(re.findall(r'class="property-card"', content))
            print(f"  Total tarjetas de propiedades: {total_cards}")
            
            # Extraer un fragmento si hay Propify
            if 'data-es-propify="true"' in content:
                idx = content.find('data-es-propify="true"')
                fragment = content[max(0, idx-200):min(len(content), idx+500)]
                print(f"  Fragmento con data-es-propify (primeros 300 chars):")
                print(f"    {fragment[:300]}...")
            else:
                # Buscar cualquier mención a propify
                idx = content.lower().find('propify')
                if idx != -1:
                    fragment = content[max(0, idx-100):min(len(content), idx+200)]
                    print(f"  Fragmento con 'propify' (primeros 200 chars):")
                    print(f"    {fragment[:200]}...")
        else:
            print(f"  ERROR: Status code {response.status_code}")
            
    except Exception as e:
        print(f"  ERROR: {e}")
    
    print()

print("=== VERIFICACIÓN COMPLETADA ===")