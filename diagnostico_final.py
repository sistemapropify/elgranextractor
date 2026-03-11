#!/usr/bin/env python
"""
Diagnóstico final del problema.
"""
import os
import sys
import django
from django.test import RequestFactory

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.views import ListaPropiedadesView

print("=== DIAGNÓSTICO FINAL ===")
print()

# Crear request factory
rf = RequestFactory()

# Caso 1: Solo Propify
print("CASO 1: Solo Propify seleccionado")
print("URL: /ingestas/propiedades/?fuente_propify=propify")
request = rf.get('/ingestas/propiedades/?fuente_propify=propify')

view = ListaPropiedadesView()
view.request = request
view.kwargs = {}

try:
    # Paso 1: Verificar checkboxes
    print("\n1. Verificando _calcular_checkboxes():")
    fuente_local, fuente_externa, fuente_propify = view._calcular_checkboxes()
    print(f"   Local: {fuente_local}, Externa: {fuente_externa}, Propify: {fuente_propify}")
    
    # Paso 2: Verificar _obtener_todas_propiedades
    print("\n2. Verificando _obtener_todas_propiedades():")
    todas_propiedades = view._obtener_todas_propiedades()
    print(f"   Total propiedades obtenidas: {len(todas_propiedades)}")
    
    # Contar tipos
    locales = sum(1 for p in todas_propiedades if not p.get('es_externo', False) and not p.get('es_propify', False))
    externas = sum(1 for p in todas_propiedades if p.get('es_externo', False) and not p.get('es_propify', False))
    propify = sum(1 for p in todas_propiedades if p.get('es_propify', False))
    
    print(f"   Desglose - Locales: {locales}, Externas: {externas}, Propify: {propify}")
    
    # Paso 3: Verificar paginación
    print("\n3. Verificando paginate_queryset():")
    paginator, page, object_list, is_paginated = view.paginate_queryset([], 12)
    print(f"   Página actual: {page.number}")
    print(f"   Objetos en página: {len(object_list)}")
    print(f"   ¿Hay paginación?: {is_paginated}")
    
    # Verificar objetos en página
    if object_list:
        print(f"   Primer objeto en página:")
        obj = object_list[0]
        print(f"     Tipo: {'Propify' if obj.get('es_propify') else 'Local' if not obj.get('es_externo') else 'Externa'}")
        print(f"     ID: {obj.get('id')}")
        print(f"     es_propify: {obj.get('es_propify')}")
        print(f"     es_externo: {obj.get('es_externo')}")
    
    # Paso 4: Verificar get_context_data
    print("\n4. Verificando get_context_data():")
    context = view.get_context_data()
    
    # Variables importantes
    important_vars = ['page', 'paginator', 'is_paginated', 'conteo_propify', 
                     'conteo_local', 'conteo_externo', 'todas_propiedades']
    
    for var in important_vars:
        if var in context:
            value = context[var]
            if var == 'page' and value:
                print(f"   {var}: {len(value.object_list) if hasattr(value, 'object_list') else 'N/A'} objetos")
            elif var == 'conteo_propify':
                print(f"   {var}: {value} (¡ESTO ES LO QUE SE MUESTRA EN EL HTML!)")
            elif var == 'todas_propiedades' and value:
                print(f"   {var}: {len(value)} propiedades")
            else:
                print(f"   {var}: {value}")
        else:
            print(f"   {var}: NO en contexto")
            
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
print("=== DIAGNÓSTICO COMPLETADO ===")