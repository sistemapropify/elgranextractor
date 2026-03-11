#!/usr/bin/env python
"""Test para verificar la lógica de checkboxes en ListaPropiedadesView"""

import os
import sys
import django

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from ingestas.views import ListaPropiedadesView

def test_checkbox_logic():
    """Test de la lógica de checkboxes"""
    factory = RequestFactory()
    
    print("=== TEST DE LÓGICA DE CHECKBOXES ===\n")
    
    # Test 1: Sin parámetros de checkbox
    print("Test 1: Sin parámetros de checkbox")
    request = factory.get('/ingestas/propiedades/')
    
    has_any_checkbox_param = any(
        key in request.GET
        for key in ['fuente_local', 'fuente_externa', 'fuente_propify']
    )
    
    if not has_any_checkbox_param:
        fuente_local = True
        fuente_externa = True
        fuente_propify = True
    else:
        fuente_local = 'fuente_local' in request.GET
        fuente_externa = 'fuente_externa' in request.GET
        fuente_propify = 'fuente_propify' in request.GET
    
    print(f"  URL: {request.path}")
    print(f"  Parámetros GET: {dict(request.GET)}")
    print(f"  has_any_checkbox_param: {has_any_checkbox_param}")
    print(f"  fuente_local: {fuente_local}")
    print(f"  fuente_externa: {fuente_externa}")
    print(f"  fuente_propify: {fuente_propify}")
    print()
    
    # Test 2: Solo fuente_propify marcada
    print("Test 2: Solo fuente_propify marcada")
    request = factory.get('/ingestas/propiedades/?fuente_propify=propify')
    
    has_any_checkbox_param = any(
        key in request.GET
        for key in ['fuente_local', 'fuente_externa', 'fuente_propify']
    )
    
    if not has_any_checkbox_param:
        fuente_local = True
        fuente_externa = True
        fuente_propify = True
    else:
        fuente_local = 'fuente_local' in request.GET
        fuente_externa = 'fuente_externa' in request.GET
        fuente_propify = 'fuente_propify' in request.GET
    
    print(f"  URL: {request.path}")
    print(f"  Parámetros GET: {dict(request.GET)}")
    print(f"  has_any_checkbox_param: {has_any_checkbox_param}")
    print(f"  fuente_local: {fuente_local}")
    print(f"  fuente_externa: {fuente_externa}")
    print(f"  fuente_propify: {fuente_propify}")
    print()
    
    # Test 3: Solo fuente_local marcada
    print("Test 3: Solo fuente_local marcada")
    request = factory.get('/ingestas/propiedades/?fuente_local=local')
    
    has_any_checkbox_param = any(
        key in request.GET
        for key in ['fuente_local', 'fuente_externa', 'fuente_propify']
    )
    
    if not has_any_checkbox_param:
        fuente_local = True
        fuente_externa = True
        fuente_propify = True
    else:
        fuente_local = 'fuente_local' in request.GET
        fuente_externa = 'fuente_externa' in request.GET
        fuente_propify = 'fuente_propify' in request.GET
    
    print(f"  URL: {request.path}")
    print(f"  Parámetros GET: {dict(request.GET)}")
    print(f"  has_any_checkbox_param: {has_any_checkbox_param}")
    print(f"  fuente_local: {fuente_local}")
    print(f"  fuente_externa: {fuente_externa}")
    print(f"  fuente_propify: {fuente_propify}")
    print()
    
    # Test 4: Solo fuente_externa marcada
    print("Test 4: Solo fuente_externa marcada")
    request = factory.get('/ingestas/propiedades/?fuente_externa=externa')
    
    has_any_checkbox_param = any(
        key in request.GET
        for key in ['fuente_local', 'fuente_externa', 'fuente_propify']
    )
    
    if not has_any_checkbox_param:
        fuente_local = True
        fuente_externa = True
        fuente_propify = True
    else:
        fuente_local = 'fuente_local' in request.GET
        fuente_externa = 'fuente_externa' in request.GET
        fuente_propify = 'fuente_propify' in request.GET
    
    print(f"  URL: {request.path}")
    print(f"  Parámetros GET: {dict(request.GET)}")
    print(f"  has_any_checkbox_param: {has_any_checkbox_param}")
    print(f"  fuente_local: {fuente_local}")
    print(f"  fuente_externa: {fuente_externa}")
    print(f"  fuente_propify: {fuente_propify}")
    print()
    
    # Test 5: Combinación de checkboxes
    print("Test 5: Combinación local + propify")
    request = factory.get('/ingestas/propiedades/?fuente_local=local&fuente_propify=propify')
    
    has_any_checkbox_param = any(
        key in request.GET
        for key in ['fuente_local', 'fuente_externa', 'fuente_propify']
    )
    
    if not has_any_checkbox_param:
        fuente_local = True
        fuente_externa = True
        fuente_propify = True
    else:
        fuente_local = 'fuente_local' in request.GET
        fuente_externa = 'fuente_externa' in request.GET
        fuente_propify = 'fuente_propify' in request.GET
    
    print(f"  URL: {request.path}")
    print(f"  Parámetros GET: {dict(request.GET)}")
    print(f"  has_any_checkbox_param: {has_any_checkbox_param}")
    print(f"  fuente_local: {fuente_local}")
    print(f"  fuente_externa: {fuente_externa}")
    print(f"  fuente_propify: {fuente_propify}")
    print()
    
    # Test 6: Con otros parámetros de filtro (sin checkboxes)
    print("Test 6: Con otros parámetros de filtro (sin checkboxes)")
    request = factory.get('/ingestas/propiedades/?tipo_propiedad=casa&precio_min=100000')
    
    has_any_checkbox_param = any(
        key in request.GET
        for key in ['fuente_local', 'fuente_externa', 'fuente_propify']
    )
    
    if not has_any_checkbox_param:
        fuente_local = True
        fuente_externa = True
        fuente_propify = True
    else:
        fuente_local = 'fuente_local' in request.GET
        fuente_externa = 'fuente_externa' in request.GET
        fuente_propify = 'fuente_propify' in request.GET
    
    print(f"  URL: {request.path}")
    print(f"  Parámetros GET: {dict(request.GET)}")
    print(f"  has_any_checkbox_param: {has_any_checkbox_param}")
    print(f"  fuente_local: {fuente_local}")
    print(f"  fuente_externa: {fuente_externa}")
    print(f"  fuente_propify: {fuente_propify}")
    print()

if __name__ == '__main__':
    test_checkbox_logic()