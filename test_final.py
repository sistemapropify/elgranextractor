#!/usr/bin/env python
"""Test final para verificar que los checkboxes funcionan"""

import requests
import re

def test_final():
    """Test final de checkboxes"""
    base_url = "http://127.0.0.1:8000/ingestas/propiedades/"
    
    print("=== TEST FINAL DE CHECKBOXES ===\n")
    
    # Test 1: Sin parámetros (deberían estar todos checked por defecto)
    print("Test 1: Sin parámetros (deberían estar todos checked)")
    response = requests.get(base_url)
    content = response.content.decode('utf-8')
    
    # Buscar checkboxes
    check_local = 'checked' in re.search(r'id="filter-fuente-local".*?>', content, re.DOTALL).group(0) if re.search(r'id="filter-fuente-local".*?>', content, re.DOTALL) else False
    check_externa = 'checked' in re.search(r'id="filter-fuente-externa".*?>', content, re.DOTALL).group(0) if re.search(r'id="filter-fuente-externa".*?>', content, re.DOTALL) else False
    check_propify = 'checked' in re.search(r'id="filter-fuente-propify".*?>', content, re.DOTALL).group(0) if re.search(r'id="filter-fuente-propify".*?>', content, re.DOTALL) else False
    
    print(f"  Local: {'CHECKED' if check_local else 'UNCHECKED'}")
    print(f"  Externa: {'CHECKED' if check_externa else 'UNCHECKED'}")
    print(f"  Propify: {'CHECKED' if check_propify else 'UNCHECKED'}")
    
    # Test 2: Solo Propify
    print("\nTest 2: Solo Propify (solo Propify debería estar checked)")
    response = requests.get(base_url + "?fuente_propify=propify")
    content = response.content.decode('utf-8')
    
    check_local = 'checked' in re.search(r'id="filter-fuente-local".*?>', content, re.DOTALL).group(0) if re.search(r'id="filter-fuente-local".*?>', content, re.DOTALL) else False
    check_externa = 'checked' in re.search(r'id="filter-fuente-externa".*?>', content, re.DOTALL).group(0) if re.search(r'id="filter-fuente-externa".*?>', content, re.DOTALL) else False
    check_propify = 'checked' in re.search(r'id="filter-fuente-propify".*?>', content, re.DOTALL).group(0) if re.search(r'id="filter-fuente-propify".*?>', content, re.DOTALL) else False
    
    print(f"  Local: {'CHECKED' if check_local else 'UNCHECKED'}")
    print(f"  Externa: {'CHECKED' if check_externa else 'UNCHECKED'}")
    print(f"  Propify: {'CHECKED' if check_propify else 'UNCHECKED'}")
    
    # Test 3: Solo Local
    print("\nTest 3: Solo Local (solo Local debería estar checked)")
    response = requests.get(base_url + "?fuente_local=local")
    content = response.content.decode('utf-8')
    
    check_local = 'checked' in re.search(r'id="filter-fuente-local".*?>', content, re.DOTALL).group(0) if re.search(r'id="filter-fuente-local".*?>', content, re.DOTALL) else False
    check_externa = 'checked' in re.search(r'id="filter-fuente-externa".*?>', content, re.DOTALL).group(0) if re.search(r'id="filter-fuente-externa".*?>', content, re.DOTALL) else False
    check_propify = 'checked' in re.search(r'id="filter-fuente-propify".*?>', content, re.DOTALL).group(0) if re.search(r'id="filter-fuente-propify".*?>', content, re.DOTALL) else False
    
    print(f"  Local: {'CHECKED' if check_local else 'UNCHECKED'}")
    print(f"  Externa: {'CHECKED' if check_externa else 'UNCHECKED'}")
    print(f"  Propify: {'CHECKED' if check_propify else 'UNCHECKED'}")
    
    # Test 4: Verificar que hay propiedades Propify en la respuesta
    print("\nTest 4: Verificar propiedades Propify en la respuesta")
    response = requests.get(base_url + "?fuente_propify=propify")
    content = response.content.decode('utf-8')
    
    # Buscar conteos
    conteo_match = re.search(r'Propiedades:\s*(\d+)', content)
    if conteo_match:
        print(f"  Total propiedades: {conteo_match.group(1)}")
    
    # Buscar tarjetas de propiedades
    prop_cards = len(re.findall(r'class="property-card"', content))
    print(f"  Tarjetas de propiedades en página: {prop_cards}")
    
    # Buscar si hay propiedades con fuente Propify
    propify_cards = len(re.findall(r'Propify DB', content))
    print(f"  Propiedades con fuente 'Propify DB': {propify_cards}")
    
    # Buscar marcadores en el mapa
    markers = len(re.findall(r'data-es-externo="true"', content))
    print(f"  Marcadores externos en mapa: {markers}")

if __name__ == '__main__':
    test_final()