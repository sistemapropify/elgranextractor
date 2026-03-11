#!/usr/bin/env python
"""Test HTTP para verificar el comportamiento real de los checkboxes"""

import requests
from bs4 import BeautifulSoup
import re

def test_checkbox_rendering():
    """Test de renderizado de checkboxes en respuestas HTTP reales"""
    base_url = "http://127.0.0.1:8000/ingestas/propiedades/"
    
    print("=== TEST DE RENDERIZADO DE CHECKBOXES HTTP ===\n")
    
    # Test 1: Sin parámetros de checkbox
    print("Test 1: Sin parámetros de checkbox")
    response = requests.get(base_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Buscar los checkboxes
    checkbox_local = soup.find('input', {'id': 'filter-fuente-local'})
    checkbox_externa = soup.find('input', {'id': 'filter-fuente-externa'})
    checkbox_propify = soup.find('input', {'id': 'filter-fuente-propify'})
    
    print(f"  Status: {response.status_code}")
    print(f"  Checkbox Local: {'checked' if checkbox_local and checkbox_local.get('checked') else 'unchecked'}")
    print(f"  Checkbox Externa: {'checked' if checkbox_externa and checkbox_externa.get('checked') else 'unchecked'}")
    print(f"  Checkbox Propify: {'checked' if checkbox_propify and checkbox_propify.get('checked') else 'unchecked'}")
    
    # Buscar conteos
    conteo_elements = soup.find_all(string=re.compile(r'Propiedades:'))
    for elem in conteo_elements[:3]:
        print(f"  {elem.strip()}")
    
    print()
    
    # Test 2: Solo fuente_propify marcada
    print("Test 2: Solo fuente_propify marcada")
    response = requests.get(base_url + "?fuente_propify=propify")
    soup = BeautifulSoup(response.content, 'html.parser')
    
    checkbox_local = soup.find('input', {'id': 'filter-fuente-local'})
    checkbox_externa = soup.find('input', {'id': 'filter-fuente-externa'})
    checkbox_propify = soup.find('input', {'id': 'filter-fuente-propify'})
    
    print(f"  Status: {response.status_code}")
    print(f"  Checkbox Local: {'checked' if checkbox_local and checkbox_local.get('checked') else 'unchecked'}")
    print(f"  Checkbox Externa: {'checked' if checkbox_externa and checkbox_externa.get('checked') else 'unchecked'}")
    print(f"  Checkbox Propify: {'checked' if checkbox_propify and checkbox_propify.get('checked') else 'unchecked'}")
    
    # Buscar conteos
    conteo_elements = soup.find_all(string=re.compile(r'Propiedades:'))
    for elem in conteo_elements[:3]:
        print(f"  {elem.strip()}")
    
    print()
    
    # Test 3: Solo fuente_local marcada
    print("Test 3: Solo fuente_local marcada")
    response = requests.get(base_url + "?fuente_local=local")
    soup = BeautifulSoup(response.content, 'html.parser')
    
    checkbox_local = soup.find('input', {'id': 'filter-fuente-local'})
    checkbox_externa = soup.find('input', {'id': 'filter-fuente-externa'})
    checkbox_propify = soup.find('input', {'id': 'filter-fuente-propify'})
    
    print(f"  Status: {response.status_code}")
    print(f"  Checkbox Local: {'checked' if checkbox_local and checkbox_local.get('checked') else 'unchecked'}")
    print(f"  Checkbox Externa: {'checked' if checkbox_externa and checkbox_externa.get('checked') else 'unchecked'}")
    print(f"  Checkbox Propify: {'checked' if checkbox_propify and checkbox_propify.get('checked') else 'unchecked'}")
    
    print()
    
    # Test 4: Solo fuente_externa marcada
    print("Test 4: Solo fuente_externa marcada")
    response = requests.get(base_url + "?fuente_externa=externa")
    soup = BeautifulSoup(response.content, 'html.parser')
    
    checkbox_local = soup.find('input', {'id': 'filter-fuente-local'})
    checkbox_externa = soup.find('input', {'id': 'filter-fuente-externa'})
    checkbox_propify = soup.find('input', {'id': 'filter-fuente-propify'})
    
    print(f"  Status: {response.status_code}")
    print(f"  Checkbox Local: {'checked' if checkbox_local and checkbox_local.get('checked') else 'unchecked'}")
    print(f"  Checkbox Externa: {'checked' if checkbox_externa and checkbox_externa.get('checked') else 'unchecked'}")
    print(f"  Checkbox Propify: {'checked' if checkbox_propify and checkbox_propify.get('checked') else 'unchecked'}")
    
    print()
    
    # Test 5: Combinación local + propify
    print("Test 5: Combinación local + propify")
    response = requests.get(base_url + "?fuente_local=local&fuente_propify=propify")
    soup = BeautifulSoup(response.content, 'html.parser')
    
    checkbox_local = soup.find('input', {'id': 'filter-fuente-local'})
    checkbox_externa = soup.find('input', {'id': 'filter-fuente-externa'})
    checkbox_propify = soup.find('input', {'id': 'filter-fuente-propify'})
    
    print(f"  Status: {response.status_code}")
    print(f"  Checkbox Local: {'checked' if checkbox_local and checkbox_local.get('checked') else 'unchecked'}")
    print(f"  Checkbox Externa: {'checked' if checkbox_externa and checkbox_externa.get('checked') else 'unchecked'}")
    print(f"  Checkbox Propify: {'checked' if checkbox_propify and checkbox_propify.get('checked') else 'unchecked'}")
    
    print()
    
    # Test 6: Con otros parámetros de filtro
    print("Test 6: Con otros parámetros de filtro (sin checkboxes)")
    response = requests.get(base_url + "?tipo_propiedad=casa&precio_min=100000")
    soup = BeautifulSoup(response.content, 'html.parser')
    
    checkbox_local = soup.find('input', {'id': 'filter-fuente-local'})
    checkbox_externa = soup.find('input', {'id': 'filter-fuente-externa'})
    checkbox_propify = soup.find('input', {'id': 'filter-fuente-propify'})
    
    print(f"  Status: {response.status_code}")
    print(f"  Checkbox Local: {'checked' if checkbox_local and checkbox_local.get('checked') else 'unchecked'}")
    print(f"  Checkbox Externa: {'checked' if checkbox_externa and checkbox_externa.get('checked') else 'unchecked'}")
    print(f"  Checkbox Propify: {'checked' if checkbox_propify and checkbox_propify.get('checked') else 'unchecked'}")

if __name__ == '__main__':
    test_checkbox_rendering()