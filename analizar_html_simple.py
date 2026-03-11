#!/usr/bin/env python
"""
Análisis simple del HTML - enfoque directo.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

# Configurar ALLOWED_HOSTS antes de setup
import django.conf as conf
conf.settings.ALLOWED_HOSTS.append('testserver')

django.setup()

from django.test import Client
import re

print("=== ANÁLISIS SIMPLE DEL HTML ===")
print()

# Crear cliente de prueba
client = Client()

# URL a probar (solo Propify)
url = "/ingestas/propiedades/?fuente_propify=propify"
print(f"Accediendo a: {url}")

try:
    response = client.get(url)
    print(f"Status code: {response.status_code}")
    
    if response.status_code == 200:
        content = response.content.decode('utf-8', errors='ignore')
        
        # Análisis básico
        print(f"Tamaño del HTML: {len(content)} caracteres")
        
        # Buscar contador de Propify
        conteo_match = re.search(r'(\d+)\s*propify', content, re.IGNORECASE)
        if conteo_match:
            print(f"Contador encontrado: {conteo_match.group(1)} propify")
        else:
            print("Contador NO encontrado - buscando '0 propify' o similar")
            # Buscar específicamente "0 propify"
            zero_match = re.search(r'0\s*propify', content, re.IGNORECASE)
            if zero_match:
                print("¡ENCONTRADO '0 propify'! Esto explica por qué el usuario no ve propiedades.")
            else:
                print("No se encontró '0 propify' tampoco")
        
        # Buscar tarjetas de propiedades
        property_cards = re.findall(r'class="property-card"', content)
        print(f"Total tarjetas de propiedades: {len(property_cards)}")
        
        # Buscar tarjetas Propify
        propify_cards = re.findall(r'data-es-propify="true"', content)
        print(f"Tarjetas con data-es-propify='true': {len(propify_cards)}")
        
        # Buscar texto "Propify"
        propify_text = len(re.findall(r'Propify', content, re.IGNORECASE))
        print(f"Texto 'Propify' aparece {propify_text} veces")
        
        # Verificar si hay propiedades en absoluto
        if len(property_cards) == 0:
            print("\n¡CRÍTICO: NO HAY TARJETAS DE PROPIEDADES EN EL HTML!")
            print("Posibles causas:")
            print("1. La vista no está devolviendo propiedades")
            print("2. El template no está renderizando las tarjetas")
            print("3. Hay un error en la paginación")
            
            # Buscar mensaje de "no hay propiedades"
            no_props = re.search(r'No hay propiedades|empty-state|sin resultados', content, re.IGNORECASE)
            if no_props:
                print(f"Se encontró mensaje de 'no hay propiedades': {no_props.group()}")
        
        # Extraer un fragmento para ver qué hay
        print("\n=== FRAGMENTO DEL HTML (primeros 2000 chars) ===")
        print(content[:2000])
        
        # Buscar información de paginación
        pagination = re.search(r'pagination.*?</nav>', content, re.DOTALL | re.IGNORECASE)
        if pagination:
            print("\n=== PAGINACIÓN ENCONTRADA ===")
            print(pagination.group()[:500])
        
    else:
        print(f"ERROR: Status code {response.status_code}")
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
print("=== ANÁLISIS COMPLETADO ===")