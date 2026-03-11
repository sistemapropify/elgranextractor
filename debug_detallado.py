#!/usr/bin/env python
"""Debug detallado del problema de checkboxes y propiedades Propify"""

import os
import sys
import django

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from ingestas.views import ListaPropiedadesView
from propifai.models import PropifaiProperty

def debug_detallado():
    """Debug detallado del problema"""
    print("=== DEBUG DETALLADO DEL PROBLEMA ===\n")
    
    # 1. Verificar que hay propiedades en Propifai
    print("1. Verificando propiedades en base de datos Propifai:")
    count = PropifaiProperty.objects.count()
    print(f"   Total propiedades en Propifai: {count}")
    
    if count > 0:
        primera = PropifaiProperty.objects.first()
        print(f"   Primera propiedad: ID={primera.id}, código={primera.code}")
        print(f"   Coordenadas: {primera.coordinates}")
        print(f"   Latitude: {primera.latitude}, Longitude: {primera.longitude}")
    
    print()
    
    # 2. Verificar la lógica de checkboxes en la vista
    print("2. Verificando lógica de checkboxes en ListaPropiedadesView:")
    
    factory = RequestFactory()
    
    # Test con diferentes URLs
    test_urls = [
        ("Sin parámetros", "/ingestas/propiedades/"),
        ("Solo Propify", "/ingestas/propiedades/?fuente_propify=propify"),
        ("Solo Local", "/ingestas/propiedades/?fuente_local=local"),
        ("Solo Externa", "/ingestas/propiedades/?fuente_externa=externa"),
        ("Local + Propify", "/ingestas/propiedades/?fuente_local=local&fuente_propify=propify"),
    ]
    
    for desc, url in test_urls:
        print(f"   {desc}:")
        request = factory.get(url)
        view = ListaPropiedadesView()
        view.request = request
        
        # Simular la lógica de get_context_data
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
        
        print(f"     Parámetros GET: {dict(request.GET)}")
        print(f"     has_any_checkbox_param: {has_any_checkbox_param}")
        print(f"     fuente_local: {fuente_local}")
        print(f"     fuente_externa: {fuente_externa}")
        print(f"     fuente_propify: {fuente_propify}")
        
        # También verificar _obtener_todas_propiedades
        try:
            todas_propiedades = view._obtener_todas_propiedades()
            conteo_locales = sum(1 for p in todas_propiedades if not p.get('es_externo') and not p.get('es_propify'))
            conteo_externas = sum(1 for p in todas_propiedades if p.get('es_externo') and not p.get('es_propify'))
            conteo_propify = sum(1 for p in todas_propiedades if p.get('es_propify'))
            print(f"     Propiedades obtenidas: {len(todas_propiedades)} total")
            print(f"       - Locales: {conteo_locales}")
            print(f"       - Externas: {conteo_externas}")
            print(f"       - Propify: {conteo_propify}")
        except Exception as e:
            print(f"     Error en _obtener_todas_propiedades: {e}")
        
        print()
    
    # 3. Verificar el método paginate_queryset
    print("3. Verificando paginate_queryset:")
    
    request = factory.get("/ingestas/propiedades/?fuente_propify=propify")
    view = ListaPropiedadesView()
    view.request = request
    
    try:
        # Obtener todas las propiedades
        todas_propiedades = view._obtener_todas_propiedades()
        print(f"   Total propiedades sin paginar: {len(todas_propiedades)}")
        
        # Simular paginación
        page_size = 12
        paginator, page, object_list, is_paginated = view.paginate_queryset(todas_propiedades, page_size)
        
        print(f"   Paginador: {paginator}")
        print(f"   Página actual: {page.number if page else 'N/A'}")
        print(f"   Objetos en página: {len(object_list) if object_list else 0}")
        print(f"   ¿Está paginado?: {is_paginated}")
        
        if object_list:
            print(f"   Primer objeto en página: {object_list[0].get('id', 'N/A') if object_list else 'N/A'}")
            # Verificar si hay propiedades Propify en la página
            propify_en_pagina = sum(1 for p in object_list if p.get('es_propify'))
            print(f"   Propiedades Propify en página: {propify_en_pagina}")
    except Exception as e:
        print(f"   Error en paginate_queryset: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # 4. Verificar el template rendering
    print("4. Verificando variables de contexto para template:")
    
    request = factory.get("/ingestas/propiedades/?fuente_propify=propify")
    view = ListaPropiedadesView()
    view.request = request
    
    try:
        # Obtener contexto
        context = view.get_context_data()
        
        print(f"   Variables en contexto:")
        print(f"     - fuente_local_checked: {context.get('fuente_local_checked', 'NO ENCONTRADA')}")
        print(f"     - fuente_externa_checked: {context.get('fuente_externa_checked', 'NO ENCONTRADA')}")
        print(f"     - fuente_propify_checked: {context.get('fuente_propify_checked', 'NO ENCONTRADA')}")
        print(f"     - conteo_locales: {context.get('conteo_locales', 'NO ENCONTRADA')}")
        print(f"     - conteo_externas: {context.get('conteo_externas', 'NO ENCONTRADA')}")
        print(f"     - conteo_propify: {context.get('conteo_propify', 'NO ENCONTRADA')}")
        print(f"     - todas_propiedades (en contexto): {len(context.get('todas_propiedades', [])) if context.get('todas_propiedades') else 0}")
        print(f"     - object_list (en contexto): {len(context.get('object_list', [])) if context.get('object_list') else 0}")
    except Exception as e:
        print(f"   Error en get_context_data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    debug_detallado()