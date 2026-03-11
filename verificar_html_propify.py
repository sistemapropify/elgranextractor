#!/usr/bin/env python
"""
Verificar el HTML generado para propiedades Propify.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

# Agregar testserver a ALLOWED_HOSTS para pruebas
from django.conf import settings
settings.ALLOWED_HOSTS.append('testserver')

from django.test import Client

client = Client()

print("=== VERIFICACIÓN HTML DE PROPIEDADES PROPIFY ===\n")

# Hacer solicitud con solo Propify
response = client.get('/ingestas/propiedades/', {'fuente_propify': 'propify'})

if response.status_code == 200:
    html = response.content.decode('utf-8', errors='ignore')
    
    print(f"1. Longitud del HTML: {len(html)} caracteres")
    
    # Buscar elementos clave
    print("\n2. Elementos clave en el HTML:")
    
    # Checkboxes
    print(f"   - 'id=\"filter-fuente-propify\"': {'ENCONTRADO' if 'id="filter-fuente-propify"' in html else 'NO ENCONTRADO'}")
    
    # Badge Propify
    print(f"   - 'badge bg-success text-white ms-1': {'ENCONTRADO' if 'badge bg-success text-white ms-1' in html else 'NO ENCONTRADO'}")
    
    # Atributos data-es-propify
    count_data_es_propify = html.count('data-es-propify="true"')
    print(f"   - 'data-es-propify=\"true\"': {count_data_es_propify} ocurrencias")
    
    # Tarjetas de propiedades
    count_property_cards = html.count('class="property-card"')
    print(f"   - 'class=\"property-card\"': {count_property_cards} ocurrencias")
    
    # Coordenadas
    count_data_lat = html.count('data-lat=')
    count_data_lng = html.count('data-lng=')
    print(f"   - 'data-lat=': {count_data_lat} ocurrencias")
    print(f"   - 'data-lng=': {count_data_lng} ocurrencias")
    
    # Códigos Propify
    count_codigo = html.count('Código:')
    print(f"   - 'Código:': {count_codigo} ocurrencias")
    
    # Buscar un fragmento con una propiedad Propify
    print("\n3. Buscando fragmentos con propiedades Propify:")
    
    # Buscar la primera ocurrencia de data-es-propify
    if 'data-es-propify="true"' in html:
        index = html.find('data-es-propify="true"')
        start = max(0, index - 300)
        end = min(len(html), index + 1000)
        fragment = html[start:end]
        
        print(f"   - Fragmento alrededor de data-es-propify=\"true\":")
        print(f"     {fragment[:500]}...")
        
        # Extraer información del fragmento
        lines = fragment.split('\n')
        for i, line in enumerate(lines[:20]):
            if any(keyword in line for keyword in ['data-lat', 'data-lng', 'Código', 'Propify', 'badge']):
                print(f"     Línea {i}: {line.strip()}")
    
    # Verificar si hay mensaje de "no hay propiedades"
    if 'No hay propiedades disponibles' in html or 'empty-state' in html:
        print("\n4. ¡ADVERTENCIA! Se encontró mensaje de 'no hay propiedades'")
    else:
        print("\n4. No se encontró mensaje de 'no hay propiedades'")
        
    # Contar propiedades por fuente en el HTML
    print("\n5. Conteo aproximado por fuente en HTML:")
    
    # Buscar badges
    count_badge_local = html.count('badge bg-warning text-dark ms-1')  # Externa
    count_badge_propify = html.count('badge bg-success text-white ms-1')  # Propify
    
    print(f"   - Badges 'Externa': {count_badge_local}")
    print(f"   - Badges 'Propify': {count_badge_propify}")
    
    # Buscar texto de fuente
    count_fuente_propify = html.count('Propify DB')
    print(f"   - Texto 'Propify DB': {count_fuente_propify}")
    
else:
    print(f"ERROR: Código de estado {response.status_code}")