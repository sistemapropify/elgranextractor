#!/usr/bin/env python3
"""
Verificación completa de la vista incluyendo el método get()
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

def verificar_vista_completa():
    """Verificar la vista completa llamando a get()"""
    print("=== VERIFICACIÓN COMPLETA DE LA VISTA ===")
    
    # Crear una request simulada con filtro solo Propify
    factory = RequestFactory()
    request = factory.get('/ingestas/propiedades/', {'fuente_propify': 'propify'})
    
    # Necesitamos un usuario para LoginRequiredMixin
    from django.contrib.auth.models import AnonymousUser
    request.user = AnonymousUser()
    
    # Instanciar y llamar a get()
    view = ListaPropiedadesView()
    view.setup(request)
    
    print("Llamando a view.get()...")
    response = view.get(request)
    
    print(f"Status code: {response.status_code}")
    print(f"Tipo de respuesta: {type(response)}")
    
    # Obtener el contexto de la respuesta
    if hasattr(response, 'context_data'):
        context = response.context_data
        print("\n--- CONTEXTO DE LA RESPUESTA ---")
        
        # Mostrar información clave
        for key in ['object_list', 'paginator', 'page_obj', 'checkboxes', 'is_paginated']:
            if key in context:
                value = context[key]
                if key == 'object_list':
                    print(f"{key}: {len(value)} elementos")
                    # Analizar los primeros 3 elementos
                    for i, prop in enumerate(value[:3]):
                        print(f"  Elemento {i}:")
                        if isinstance(prop, dict):
                            print(f"    Tipo: dict")
                            print(f"    es_propify: {prop.get('es_propify', 'NO EXISTE')}")
                            print(f"    es_externo: {prop.get('es_externo', 'NO EXISTE')}")
                            print(f"    id: {prop.get('id', prop.get('id_externo', 'NO EXISTE'))}")
                            print(f"    lat/lng: {prop.get('lat', 'N/A')}, {prop.get('lng', 'N/A')}")
                        else:
                            print(f"    Tipo: {type(prop)}")
                            print(f"    str: {str(prop)[:100]}")
                elif key == 'checkboxes':
                    print(f"{key}: {value}")
                else:
                    print(f"{key}: {value}")
        
        # Contar propiedades por tipo
        object_list = context.get('object_list', [])
        print(f"\n--- ANÁLISIS DE PROPIEDADES ---")
        print(f"Total propiedades: {len(object_list)}")
        
        propify_count = 0
        externo_count = 0
        local_count = 0
        otros_count = 0
        
        for prop in object_list:
            if isinstance(prop, dict):
                if prop.get('es_propify'):
                    propify_count += 1
                elif prop.get('es_externo'):
                    externo_count += 1
                else:
                    local_count += 1
            else:
                otros_count += 1
        
        print(f"Propiedades Propify: {propify_count}")
        print(f"Propiedades Externas: {externo_count}")
        print(f"Propiedades Locales: {local_count}")
        print(f"Otros tipos: {otros_count}")
        
        # Verificar que todas sean Propify cuando filtramos solo Propify
        if propify_count > 0 and externo_count == 0 and local_count == 0:
            print("✓ FILTRO CORRECTO: Solo se muestran propiedades Propify")
        else:
            print("✗ FILTRO INCORRECTO: Se muestran propiedades de otros tipos")
            
        # Verificar coordenadas
        print(f"\n--- VERIFICACIÓN DE COORDENADAS ---")
        propify_con_coords = 0
        for prop in object_list:
            if isinstance(prop, dict) and prop.get('es_propify'):
                lat = prop.get('lat')
                lng = prop.get('lng')
                if lat is not None and lng is not None:
                    propify_con_coords += 1
        
        print(f"Propiedades Propify con coordenadas: {propify_con_coords}/{propify_count}")
        
        # Verificar paginación
        print(f"\n--- PAGINACIÓN ---")
        page_obj = context.get('page_obj')
        if page_obj:
            print(f"Página actual: {page_obj.number}")
            print(f"Total páginas: {page_obj.paginator.num_pages}")
            print(f"Propiedades por página: {len(page_obj.object_list)}")
    
    # También verificar sin filtros
    print("\n=== VERIFICACIÓN SIN FILTROS ===")
    request2 = factory.get('/ingestas/propiedades/')
    request2.user = AnonymousUser()
    
    view2 = ListaPropiedadesView()
    view2.setup(request2)
    response2 = view2.get(request2)
    
    if hasattr(response2, 'context_data'):
        context2 = response2.context_data
        object_list2 = context2.get('object_list', [])
        
        # Contar por tipo
        propify2 = sum(1 for p in object_list2 if isinstance(p, dict) and p.get('es_propify'))
        externo2 = sum(1 for p in object_list2 if isinstance(p, dict) and p.get('es_externo') and not p.get('es_propify'))
        local2 = sum(1 for p in object_list2 if isinstance(p, dict) and not p.get('es_externo'))
        
        print(f"Total propiedades (sin filtro): {len(object_list2)}")
        print(f"  Propify: {propify2}")
        print(f"  Externas: {externo2}")
        print(f"  Locales: {local2}")
        
        # Verificar intercalado
        print(f"\n--- VERIFICACIÓN DE INTERCALADO ---")
        if len(object_list2) > 10:
            # Verificar el patrón en las primeras 10 propiedades
            tipos = []
            for i, prop in enumerate(object_list2[:10]):
                if isinstance(prop, dict):
                    if prop.get('es_propify'):
                        tipos.append('P')
                    elif prop.get('es_externo'):
                        tipos.append('E')
                    else:
                        tipos.append('L')
                else:
                    tipos.append('?')
            
            print(f"Patrón de tipos (primeras 10): {''.join(tipos)}")
            
            # Verificar que no haya más de 2 del mismo tipo consecutivas
            consecutivas = 0
            max_consecutivas = 0
            current_type = None
            for t in tipos:
                if t == current_type:
                    consecutivas += 1
                    max_consecutivas = max(max_consecutivas, consecutivas)
                else:
                    current_type = t
                    consecutivas = 1
            
            if max_consecutivas <= 2:
                print("✓ INTERCALADO CORRECTO: No hay más de 2 propiedades del mismo tipo consecutivas")
            else:
                print(f"✗ INTERCALADO PROBLEMÁTICO: Hay {max_consecutivas} propiedades del mismo tipo consecutivas")

def verificar_problemas_potenciales():
    """Verificar problemas potenciales en el código"""
    print("\n=== VERIFICACIÓN DE PROBLEMAS POTENCIALES ===")
    
    # Leer el archivo de views.py para verificar
    views_path = os.path.join('webapp', 'ingestas', 'views.py')
    with open(views_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Buscar problemas comunes
    problemas = []
    
    # 1. Verificar que _convertir_propiedad_propifai_a_dict establezca es_propify=True
    if 'es_propify\": True' not in content and "'es_propify': True" not in content:
        problemas.append("No se encuentra es_propify=True en _convertir_propiedad_propifai_a_dict")
    else:
        print("✓ es_propify=True está presente en el código")
    
    # 2. Verificar que el template use data-es-propify
    template_path = os.path.join('webapp', 'templates', 'ingestas', 'lista_propiedades_rediseno.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    if 'data-es-propify' not in template_content:
        problemas.append("El template no tiene data-es-propify")
    else:
        print("✓ data-es-propify está presente en el template")
    
    if 'Propify' not in template_content:
        problemas.append("El template no muestra 'Propify'")
    else:
        print("✓ 'Propify' está presente en el template")
    
    # 3. Verificar el JavaScript para marcadores
    if 'esPropify' not in template_content:
        problemas.append("JavaScript no maneja esPropify")
    else:
        print("✓ JavaScript maneja esPropify")
    
    if problemas:
        print("\n✗ PROBLEMAS ENCONTRADOS:")
        for p in problemas:
            print(f"  - {p}")
    else:
        print("\n✓ No se encontraron problemas evidentes en el código")

if __name__ == "__main__":
    verificar_vista_completa()
    verificar_problemas_potenciales()
    print("\n=== VERIFICACIÓN COMPLETADA ===")