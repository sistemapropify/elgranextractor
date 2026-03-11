#!/usr/bin/env python
"""
Verificación directa del HTML generado por la vista.
"""
import os
import sys
import django
from django.test import Client

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

print("=== VERIFICACIÓN DIRECTA DEL HTML GENERADO ===")
print()

# Crear cliente de prueba
client = Client()

# Probar diferentes URLs
test_urls = [
    ("URL sin filtros", "/ingestas/propiedades/"),
    ("URL solo Propify", "/ingestas/propiedades/?fuente_propify=propify"),
    ("URL solo locales", "/ingestas/propiedades/?fuente_local=local"),
    ("URL solo externas", "/ingestas/propiedades/?fuente_externa=externa"),
]

for name, url in test_urls:
    print(f"Probando: {name}")
    print(f"URL: {url}")
    
    try:
        response = client.get(url)
        print(f"  Status code: {response.status_code}")
        
        if response.status_code == 200:
            content = response.content.decode('utf-8', errors='ignore')
            
            # Buscar contadores en el HTML
            import re
            
            # Buscar "propify" en el HTML (case insensitive)
            propify_matches = re.findall(r'propify', content, re.IGNORECASE)
            print(f"  'propify' aparece {len(propify_matches)} veces en el HTML")
            
            # Buscar contador específico
            conteo_match = re.search(r'(\d+)\s*propify', content, re.IGNORECASE)
            if conteo_match:
                print(f"  Contador encontrado: {conteo_match.group(1)} propify")
            else:
                print(f"  Contador NO encontrado en HTML")
                
            # Buscar propiedades Propify en el HTML
            propify_cards = re.findall(r'data-es-propify="true"', content)
            print(f"  Tarjetas con data-es-propify='true': {len(propify_cards)}")
            
            # Buscar "Propify" como texto en las tarjetas
            propify_text = re.findall(r'Propify', content)
            print(f"  Texto 'Propify' aparece {len(propify_text)} veces")
            
            # Verificar si hay propiedades en general
            property_cards = re.findall(r'class="property-card"', content)
            print(f"  Total tarjetas de propiedades: {len(property_cards)}")
            
            # Extraer un fragmento del HTML para inspección
            if 'data-es-propify="true"' in content:
                idx = content.find('data-es-propify="true"')
                fragment = content[max(0, idx-200):min(len(content), idx+500)]
                print(f"  Fragmento HTML con data-es-propify:")
                print(f"    {fragment[:200]}...")
        else:
            print(f"  ERROR: Status code no es 200")
            
    except Exception as e:
        print(f"  ERROR: {e}")
    
    print()

print("=== VERIFICACIÓN COMPLETADA ===")