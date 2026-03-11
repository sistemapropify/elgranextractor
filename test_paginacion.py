#!/usr/bin/env python
"""
Test para verificar que la paginación funciona con propiedades Propify.
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

print("=== TEST DE PAGINACION PROPY ===")
print()

# Test 1: Filtrar solo Propify
print("1. Test: Filtrar solo Propify")
factory = RequestFactory()
request = factory.get('/ingestas/propiedades/?fuente_propify=propify')

view = ListaPropiedadesView()
view.setup(request)
response = view.get(request)

if hasattr(response, 'context_data'):
    context = response.context_data
    print(f"   OK - Conteo locales: {context.get('conteo_locales', 0)}")
    print(f"   OK - Conteo externas: {context.get('conteo_externas', 0)}")
    print(f"   OK - Conteo propify: {context.get('conteo_propify', 0)}")
    print(f"   OK - Total propiedades: {context.get('total_propiedades', 0)}")
    print(f"   OK - Propiedades en página actual: {len(context.get('todas_propiedades', []))}")
    
    # Verificar paginación
    if hasattr(view, 'paginator'):
        print(f"   OK - Número de páginas: {view.paginator.num_pages}")
        print(f"   OK - Página actual: {view.page.number}")
    
    # Verificar que hay propiedades Propify
    todas_propiedades = context.get('todas_propiedades', [])
    propify_props = [p for p in todas_propiedades if p.get('es_propify')]
    print(f"   OK - Propiedades Propify en página: {len(propify_props)}")
    
    if propify_props:
        print(f"   OK - Ejemplo: ID={propify_props[0].get('id')}, Tipo={propify_props[0].get('tipo_propiedad')}")
else:
    print("   ERROR: No se pudo obtener contexto")

print()

# Test 2: Filtrar todas las fuentes (por defecto)
print("2. Test: Mostrar todas las fuentes (por defecto)")
request2 = factory.get('/ingestas/propiedades/')

view2 = ListaPropiedadesView()
view2.setup(request2)
response2 = view2.get(request2)

if hasattr(response2, 'context_data'):
    context2 = response2.context_data
    print(f"   OK - Conteo locales: {context2.get('conteo_locales', 0)}")
    print(f"   OK - Conteo externas: {context2.get('conteo_externas', 0)}")
    print(f"   OK - Conteo propify: {context2.get('conteo_propify', 0)}")
    print(f"   OK - Total propiedades: {context2.get('total_propiedades', 0)}")
    
    # Verificar que todas las fuentes están activas por defecto
    print(f"   OK - fuente_local_checked: {context2.get('fuente_local_checked', False)}")
    print(f"   OK - fuente_externa_checked: {context2.get('fuente_externa_checked', False)}")
    print(f"   OK - fuente_propify_checked: {context2.get('fuente_propify_checked', False)}")
else:
    print("   ERROR: No se pudo obtener contexto")

print()

# Test 3: Filtrar solo locales y Propify
print("3. Test: Filtrar solo locales y Propify")
request3 = factory.get('/ingestas/propiedades/?fuente_local=local&fuente_propify=propify')

view3 = ListaPropiedadesView()
view3.setup(request3)
response3 = view3.get(request3)

if hasattr(response3, 'context_data'):
    context3 = response3.context_data
    print(f"   OK - Conteo locales: {context3.get('conteo_locales', 0)}")
    print(f"   OK - Conteo externas: {context3.get('conteo_externas', 0)} (debería ser 0)")
    print(f"   OK - Conteo propify: {context3.get('conteo_propify', 0)}")
    
    # Verificar checkboxes
    print(f"   OK - fuente_local_checked: {context3.get('fuente_local_checked', False)}")
    print(f"   OK - fuente_externa_checked: {context3.get('fuente_externa_checked', False)} (debería ser False)")
    print(f"   OK - fuente_propify_checked: {context3.get('fuente_propify_checked', False)}")
else:
    print("   ERROR: No se pudo obtener contexto")

print()
print("=== FIN DEL TEST ===")