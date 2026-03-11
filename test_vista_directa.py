#!/usr/bin/env python3
"""
Test directo de la vista para ver qué está pasando
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from ingestas.views import ListaPropiedadesView

print("=== TEST DIRECTO DE LA VISTA ===")

# Crear request con filtro solo Propify
factory = RequestFactory()
request = factory.get('/ingestas/propiedades/', {'fuente_propify': 'propify'})

# Crear vista
view = ListaPropiedadesView()
view.setup(request)

print("1. Probando _calcular_checkboxes()...")
try:
    fuente_local, fuente_externa, fuente_propify = view._calcular_checkboxes()
    print(f"   Resultado: Local={fuente_local}, Externa={fuente_externa}, Propify={fuente_propify}")
except Exception as e:
    print(f"   Error: {e}")

print("\n2. Probando _obtener_todas_propiedades()...")
try:
    todas = view._obtener_todas_propiedades()
    print(f"   Total propiedades obtenidas: {len(todas)}")
    
    # Contar por tipo
    propify_count = sum(1 for p in todas if isinstance(p, dict) and p.get('es_propify'))
    externo_count = sum(1 for p in todas if isinstance(p, dict) and p.get('es_externo') and not p.get('es_propify'))
    local_count = sum(1 for p in todas if isinstance(p, dict) and not p.get('es_externo'))
    
    print(f"   Propify: {propify_count}")
    print(f"   Externas: {externo_count}")
    print(f"   Locales: {local_count}")
    
    # Mostrar primera propiedad si es Propify
    if propify_count > 0:
        primera_propify = next(p for p in todas if isinstance(p, dict) and p.get('es_propify'))
        print(f"\n   Primera propiedad Propify:")
        print(f"     ID: {primera_propify.get('id')}")
        print(f"     es_propify: {primera_propify.get('es_propify')}")
        print(f"     es_externo: {primera_propify.get('es_externo')}")
        print(f"     lat/lng: {primera_propify.get('lat')}, {primera_propify.get('lng')}")
    else:
        print("\n   ADVERTENCIA: No hay propiedades Propify en _obtener_todas_propiedades()")
        
except Exception as e:
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()

print("\n3. Probando paginate_queryset()...")
try:
    # Llamar a paginate_queryset
    paginator, page, object_list, is_paginated = view.paginate_queryset(None, 12)
    print(f"   Total páginas: {paginator.num_pages}")
    print(f"   Propiedades en página 1: {len(object_list)}")
    print(f"   Es paginado: {is_paginated}")
    
    # Verificar object_list
    propify_in_page = sum(1 for p in object_list if isinstance(p, dict) and p.get('es_propify'))
    print(f"   Propify en página 1: {propify_in_page}")
    
except Exception as e:
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()

print("\n4. Probando get_context_data()...")
try:
    # Necesitamos establecer object_list primero
    view.object_list = object_list if 'object_list' in locals() else []
    
    context = view.get_context_data()
    print(f"   Conteos en contexto:")
    print(f"     conteo_locales: {context.get('conteo_locales')}")
    print(f"     conteo_externas: {context.get('conteo_externas')}")
    print(f"     conteo_propify: {context.get('conteo_propify')}")
    print(f"     total_propiedades: {context.get('total_propiedades')}")
    
    # Verificar todas_propiedades en contexto
    todas_en_contexto = context.get('todas_propiedades', [])
    print(f"   Propiedades en 'todas_propiedades' del contexto: {len(todas_en_contexto)}")
    
except Exception as e:
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== TEST COMPLETADO ===")