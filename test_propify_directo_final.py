#!/usr/bin/env python
"""
Test directo para verificar propiedades Propify en la vista.
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

print("=== TEST DIRECTO DE PROPIEDADES PROPIY ===")
print()

# Crear request factory
rf = RequestFactory()

# Caso 1: Solo Propify seleccionado
print("1. Probando con solo Propify seleccionado...")
request = rf.get('/ingestas/propiedades/?fuente_propify=propify')

view = ListaPropiedadesView()
view.request = request
view.kwargs = {}

# Obtener contexto
context = view.get_context_data()

print(f"   Total propiedades: {context.get('total_propiedades', 'NO ENCONTRADO')}")
print(f"   Conteo locales: {context.get('conteo_locales', 'NO ENCONTRADO')}")
print(f"   Conteo externas: {context.get('conteo_externas', 'NO ENCONTRADO')}")
print(f"   Conteo propify: {context.get('conteo_propify', 'NO ENCONTRADO')}")

# Verificar propiedades en object_list
object_list = context.get('todas_propiedades', [])
print(f"   Propiedades en object_list: {len(object_list)}")

# Contar Propify en object_list
propify_count = 0
if object_list:
    for i, prop in enumerate(object_list[:3]):  # Mostrar primeras 3
        print(f"   Propiedad {i+1}:")
        print(f"     Tipo: {type(prop)}")
        if isinstance(prop, dict):
            print(f"     Es propify: {prop.get('es_propify', False)}")
            print(f"     Es externo: {prop.get('es_externo', False)}")
            print(f"     ID: {prop.get('id', 'N/A')}")
            print(f"     Lat: {prop.get('lat', 'N/A')}")
            print(f"     Lng: {prop.get('lng', 'N/A')}")
            if prop.get('es_propify'):
                propify_count += 1
        else:
            print(f"     No es diccionario: {prop}")
        print()

print(f"   Total Propify en object_list: {propify_count}")

# Caso 2: Todas las fuentes
print("\n2. Probando con todas las fuentes (sin filtros)...")
request2 = rf.get('/ingestas/propiedades/')
view2 = ListaPropiedadesView()
view2.request = request2
view2.kwargs = {}

context2 = view2.get_context_data()
print(f"   Total propiedades: {context2.get('total_propiedades', 'NO ENCONTRADO')}")
print(f"   Conteo locales: {context2.get('conteo_locales', 'NO ENCONTRADO')}")
print(f"   Conteo externas: {context2.get('conteo_externas', 'NO ENCONTRADO')}")
print(f"   Conteo propify: {context2.get('conteo_propify', 'NO ENCONTRADO')}")

print("\n=== TEST COMPLETADO ===")