#!/usr/bin/env python
"""
Test simple para depurar la paginación.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from ingestas.views import ListaPropiedadesView

print("=== DEPURACION SIMPLE ===")
print()

# Test 1: Verificar _obtener_todas_propiedades
print("1. Verificando _obtener_todas_propiedades...")
factory = RequestFactory()
request = factory.get('/ingestas/propiedades/?fuente_propify=propify')

view = ListaPropiedadesView()
view.request = request

# Llamar a _obtener_todas_propiedades directamente
todas_propiedades = view._obtener_todas_propiedades()
print(f"   Total propiedades obtenidas: {len(todas_propiedades)}")

if todas_propiedades:
    # Verificar el tipo del primer elemento
    primer_elemento = todas_propiedades[0]
    print(f"   Tipo del primer elemento: {type(primer_elemento)}")
    
    # Verificar si es diccionario
    if isinstance(primer_elemento, dict):
        print(f"   Es diccionario: SI")
        print(f"   Keys: {list(primer_elemento.keys())[:5]}...")
        print(f"   Tiene es_propify: {'es_propify' in primer_elemento}")
    else:
        print(f"   Es diccionario: NO")
        print(f"   Atributos disponibles: {dir(primer_elemento)[:10]}...")

print()

# Test 2: Verificar paginate_queryset
print("2. Verificando paginate_queryset...")
try:
    # Configurar view
    view.setup(request)
    
    # Llamar a paginate_queryset
    result = view.paginate_queryset(view.get_queryset(), view.paginate_by)
    print(f"   Resultado de paginate_queryset: {type(result)}")
    
    if isinstance(result, tuple) and len(result) == 4:
        paginator, page, object_list, is_paginated = result
        print(f"   Paginator: {paginator}")
        print(f"   Page number: {page.number}")
        print(f"   Object list length: {len(object_list)}")
        print(f"   Is paginated: {is_paginated}")
        
        if object_list:
            primer_obj = object_list[0]
            print(f"   Tipo en object_list: {type(primer_obj)}")
    else:
        print(f"   ERROR: Resultado no es tupla de 4 elementos")
        
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 3: Verificar get_context_data
print("3. Verificando get_context_data...")
try:
    context = view.get_context_data()
    print(f"   Conteo locales: {context.get('conteo_locales', 0)}")
    print(f"   Conteo externas: {context.get('conteo_externas', 0)}")
    print(f"   Conteo propify: {context.get('conteo_propify', 0)}")
    print(f"   Total propiedades: {context.get('total_propiedades', 0)}")
    
    todas_propiedades_ctx = context.get('todas_propiedades', [])
    print(f"   Propiedades en contexto: {len(todas_propiedades_ctx)}")
    
    if todas_propiedades_ctx:
        primer_elem = todas_propiedades_ctx[0]
        print(f"   Tipo en contexto: {type(primer_elem)}")
        
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
print("=== FIN DEPURACION ===")