#!/usr/bin/env python
"""Test simple para verificar variables de contexto"""

import os
import sys
import django

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory, Client
from django.template import Template, Context

def test_contexto_simple():
    """Test simple de variables de contexto"""
    print("=== TEST SIMPLE DE VARIABLES DE CONTEXTO ===\n")
    
    # Usar cliente de test para obtener respuesta real
    client = Client()
    
    # Test 1: Sin parámetros
    print("Test 1: Sin parámetros")
    response = client.get('/ingestas/propiedades/')
    print(f"  Status: {response.status_code}")
    
    # Verificar si el template tiene las variables
    if response.context:
        print(f"  Contexto disponible: Sí")
        context = response.context
        print(f"  fuente_local_checked: {context.get('fuente_local_checked', 'NO ENCONTRADA')}")
        print(f"  fuente_externa_checked: {context.get('fuente_externa_checked', 'NO ENCONTRADA')}")
        print(f"  fuente_propify_checked: {context.get('fuente_propify_checked', 'NO ENCONTRADA')}")
    else:
        print(f"  Contexto disponible: No")
    
    # Extraer HTML y buscar checkboxes
    content = response.content.decode('utf-8')
    
    # Buscar los checkboxes en el HTML
    import re
    
    # Buscar checkbox local
    local_match = re.search(r'id="filter-fuente-local".*?(checked|>)', content, re.DOTALL)
    if local_match:
        print(f"  Checkbox Local en HTML: {'checked' if 'checked' in local_match.group(0) else 'unchecked'}")
    
    # Buscar checkbox externa
    externa_match = re.search(r'id="filter-fuente-externa".*?(checked|>)', content, re.DOTALL)
    if externa_match:
        print(f"  Checkbox Externa en HTML: {'checked' if 'checked' in externa_match.group(0) else 'unchecked'}")
    
    # Buscar checkbox propify
    propify_match = re.search(r'id="filter-fuente-propify".*?(checked|>)', content, re.DOTALL)
    if propify_match:
        print(f"  Checkbox Propify en HTML: {'checked' if 'checked' in propify_match.group(0) else 'unchecked'}")
    
    print()
    
    # Test 2: Solo Propify
    print("Test 2: Solo Propify")
    response = client.get('/ingestas/propiedades/?fuente_propify=propify')
    print(f"  Status: {response.status_code}")
    
    if response.context:
        print(f"  Contexto disponible: Sí")
        context = response.context
        print(f"  fuente_local_checked: {context.get('fuente_local_checked', 'NO ENCONTRADA')}")
        print(f"  fuente_externa_checked: {context.get('fuente_externa_checked', 'NO ENCONTRADA')}")
        print(f"  fuente_propify_checked: {context.get('fuente_propify_checked', 'NO ENCONTRADA')}")
    else:
        print(f"  Contexto disponible: No")
    
    content = response.content.decode('utf-8')
    
    # Buscar checkbox propify
    propify_match = re.search(r'id="filter-fuente-propify".*?(checked|>)', content, re.DOTALL)
    if propify_match:
        print(f"  Checkbox Propify en HTML: {'checked' if 'checked' in propify_match.group(0) else 'unchecked'}")
    
    print()
    
    # Test 3: Verificar conteos
    print("Test 3: Verificar conteos en respuesta")
    response = client.get('/ingestas/propiedades/?fuente_propify=propify')
    
    if response.context:
        context = response.context
        print(f"  conteo_locales: {context.get('conteo_locales', 'NO ENCONTRADA')}")
        print(f"  conteo_externas: {context.get('conteo_externas', 'NO ENCONTRADA')}")
        print(f"  conteo_propify: {context.get('conteo_propify', 'NO ENCONTRADA')}")
        print(f"  total_propiedades: {context.get('total_propiedades', 'NO ENCONTRADA')}")
        
        # Verificar object_list
        object_list = context.get('object_list', [])
        print(f"  object_list (paginado): {len(object_list) if object_list else 0} elementos")
        
        # Contar Propify en object_list
        if object_list:
            propify_count = sum(1 for p in object_list if hasattr(p, 'get') and p.get('es_propify'))
            print(f"  Propify en object_list: {propify_count}")

if __name__ == '__main__':
    test_contexto_simple()