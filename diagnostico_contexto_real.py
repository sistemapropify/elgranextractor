#!/usr/bin/env python
"""
Diagnóstico del contexto real en producción.
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

print("=== DIAGNÓSTICO DEL CONTEXTO REAL ===")
print()

# Crear request factory
rf = RequestFactory()

# Caso: Solo Propify
print("CASO: Solo Propify seleccionado")
request = rf.get('/ingestas/propiedades/?fuente_propify=propify')

view = ListaPropiedadesView()
view.request = request
view.kwargs = {}

try:
    # Simular el flujo completo de Django
    print("\n1. Simulando dispatch()...")
    
    # Django normalmente llama a dispatch() que llama a get()
    # Para simplificar, llamaremos directamente a los métodos necesarios
    
    # Paso 1: get_queryset
    print("   Llamando a get_queryset()...")
    queryset = view.get_queryset()
    print(f"   Queryset: {queryset.count()} propiedades locales")
    
    # Paso 2: paginate_queryset
    print("   Llamando a paginate_queryset()...")
    paginator, page, object_list, is_paginated = view.paginate_queryset(queryset, 12)
    
    print(f"   Paginator.count: {paginator.count}")
    print(f"   Page.number: {page.number}")
    print(f"   Object_list length: {len(object_list)}")
    print(f"   Is_paginated: {is_paginated}")
    
    # Verificar object_list
    print(f"\n2. Analizando object_list...")
    if object_list:
        print(f"   Total objetos: {len(object_list)}")
        
        # Verificar tipos
        tipos = {}
        for obj in object_list:
            tipo = "desconocido"
            if isinstance(obj, dict):
                if obj.get('es_propify'):
                    tipo = "propify"
                elif obj.get('es_externo'):
                    tipo = "externa"
                else:
                    tipo = "local"
            else:
                tipo = f"no-dict: {type(obj)}"
            tipos[tipo] = tipos.get(tipo, 0) + 1
        
        print(f"   Tipos encontrados:")
        for tipo, count in tipos.items():
            print(f"     {tipo}: {count}")
            
        # Mostrar primeros objetos
        print(f"\n   Primeros 3 objetos:")
        for i, obj in enumerate(object_list[:3]):
            print(f"   {i+1}. Tipo: {type(obj)}")
            if isinstance(obj, dict):
                print(f"      es_propify: {obj.get('es_propify')}")
                print(f"      es_externo: {obj.get('es_externo')}")
                print(f"      id: {obj.get('id')}")
                print(f"      tipo_propiedad: {obj.get('tipo_propiedad')}")
            else:
                print(f"      Objeto no es dict: {obj}")
    
    # Paso 3: get_context_data
    print(f"\n3. Llamando a get_context_data()...")
    
    # Establecer atributos necesarios
    view.object_list = object_list
    view.paginator = paginator
    view.page = page
    
    context = view.get_context_data()
    
    print(f"   Contexto tiene {len(context)} variables")
    
    # Variables críticas
    print(f"\n4. Variables críticas en contexto:")
    
    critical_vars = [
        'conteo_propify', 'conteo_local', 'conteo_externo',
        'todas_propiedades', 'page', 'object_list',
        'fuente_propify_checked', 'fuente_local_checked', 'fuente_externa_checked'
    ]
    
    for var in critical_vars:
        if var in context:
            value = context[var]
            if var == 'conteo_propify':
                print(f"   {var}: {value} (¡ESTO ES CLAVE!)")
            elif var == 'todas_propiedades':
                if value:
                    print(f"   {var}: {len(value)} propiedades")
                    
                    # Contar Propify
                    propify_count = sum(1 for p in value if isinstance(p, dict) and p.get('es_propify'))
                    print(f"      -> Propify en todas_propiedades: {propify_count}")
                    
                    # Verificar primeros elementos
                    if value:
                        first = value[0]
                        print(f"      -> Primer elemento: tipo={type(first)}, es_propify={first.get('es_propify') if isinstance(first, dict) else 'N/A'}")
                else:
                    print(f"   {var}: VACÍO o None")
            elif var == 'page' and value:
                if hasattr(value, 'object_list'):
                    print(f"   {var}: {len(value.object_list)} objetos")
                else:
                    print(f"   {var}: {value} (sin object_list)")
            else:
                print(f"   {var}: {value}")
        else:
            print(f"   {var}: NO en contexto")
            
    # Paso 5: Verificar si hay discrepancia
    print(f"\n5. Verificando discrepancia...")
    
    if 'conteo_propify' in context and context['conteo_propify'] > 0:
        if 'todas_propiedades' in context and context['todas_propiedades']:
            propify_in_todas = sum(1 for p in context['todas_propiedades'] if isinstance(p, dict) and p.get('es_propify'))
            print(f"   conteo_propify dice: {context['conteo_propify']}")
            print(f"   Propify en todas_propiedades: {propify_in_todas}")
            
            if context['conteo_propify'] != propify_in_todas:
                print(f"   ¡DISCREPANCIA! Los números no coinciden")
            else:
                print(f"   ✓ Los números coinciden")
        else:
            print(f"   ¡PROBLEMA: todas_propiedades está vacío!")
    else:
        print(f"   ¡PROBLEMA: conteo_propify es 0 o no existe!")
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
print("=== DIAGNÓSTICO COMPLETADO ===")