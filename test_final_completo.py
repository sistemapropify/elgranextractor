#!/usr/bin/env python
"""
Test final completo después de las correcciones.
"""
import os
import sys
import django
from django.test import RequestFactory, TestCase

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.views import ListaPropiedadesView

print("=== TEST FINAL COMPLETO ===")
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
    # Paso 1: Verificar que la vista completa funcione
    print("\n1. Ejecutando vista completa...")
    
    # Llamar a get_queryset (aunque no lo usamos directamente)
    queryset = view.get_queryset()
    print(f"   Queryset original: {queryset.count()} propiedades locales")
    
    # Llamar a paginate_queryset
    print("   Ejecutando paginate_queryset...")
    paginator, page, object_list, is_paginated = view.paginate_queryset(queryset, 12)
    
    print(f"   Paginador: {paginator.count} propiedades totales")
    print(f"   Página: {page.number} de {paginator.num_pages}")
    print(f"   Object_list: {len(object_list)} propiedades en página")
    print(f"   ¿Hay paginación?: {is_paginated}")
    
    # Verificar object_list
    if object_list:
        print(f"\n   Primeras 3 propiedades en object_list:")
        for i, obj in enumerate(object_list[:3]):
            print(f"   {i+1}. ID: {obj.get('id')}, "
                  f"Tipo: {'Propify' if obj.get('es_propify') else 'Local' if not obj.get('es_externo') else 'Externa'}, "
                  f"es_propify: {obj.get('es_propify')}")
    
    # Paso 2: Verificar get_context_data
    print("\n2. Ejecutando get_context_data...")
    
    # Necesitamos establecer object_list en la vista primero
    view.object_list = object_list
    view.paginator = paginator
    view.page = page
    
    context = view.get_context_data()
    
    print(f"   Contexto obtenido con {len(context)} variables")
    
    # Variables críticas
    critical_vars = ['conteo_propify', 'conteo_local', 'conteo_externo', 'todas_propiedades', 'page']
    
    for var in critical_vars:
        if var in context:
            value = context[var]
            if var == 'conteo_propify':
                print(f"   {var}: {value} (¡ESTO DEBE SER > 0!)")
                if value == 0:
                    print("      ¡ERROR: conteo_propify es 0!")
                else:
                    print("      ✓ CORRECTO: Hay propiedades Propify")
            elif var == 'todas_propiedades':
                print(f"   {var}: {len(value) if value else 0} propiedades")
                
                # Contar Propify en todas_propiedades
                if value:
                    propify_count = sum(1 for p in value if p.get('es_propify', False))
                    print(f"      -> De ellas, {propify_count} son Propify")
            elif var == 'page':
                if value and hasattr(value, 'object_list'):
                    print(f"   {var}: {len(value.object_list)} objetos en página")
                    
                    # Verificar si hay Propify en la página
                    propify_in_page = sum(1 for p in value.object_list if p.get('es_propify', False))
                    print(f"      -> De ellos, {propify_in_page} son Propify")
            else:
                print(f"   {var}: {value}")
        else:
            print(f"   {var}: NO en contexto")
    
    # Paso 3: Verificar que las propiedades Propify tengan los campos correctos
    print("\n3. Verificando campos de propiedades Propify...")
    
    if 'todas_propiedades' in context and context['todas_propiedades']:
        propify_props = [p for p in context['todas_propiedades'] if p.get('es_propify', False)]
        
        if propify_props:
            print(f"   Se encontraron {len(propify_props)} propiedades Propify")
            
            # Verificar primera propiedad
            first_prop = propify_props[0]
            required_fields = ['id', 'tipo_propiedad', 'precio_usd', 'lat', 'lng', 'es_propify', 'es_externo']
            
            print(f"   Campos de la primera propiedad Propify:")
            for field in required_fields:
                value = first_prop.get(field)
                if value is not None:
                    print(f"      {field}: {value}")
                else:
                    print(f"      {field}: ¡FALTANTE o None!")
                    
            # Verificar coordenadas
            lat = first_prop.get('lat')
            lng = first_prop.get('lng')
            if lat and lng:
                print(f"      Coordenadas válidas: ({lat}, {lng})")
            else:
                print(f"      ¡ERROR: Coordenadas faltantes!")
        else:
            print("   ¡ERROR: No se encontraron propiedades Propify en todas_propiedades!")
    else:
        print("   ¡ERROR: todas_propiedades no está en el contexto o está vacía!")
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
print("=== TEST COMPLETADO ===")