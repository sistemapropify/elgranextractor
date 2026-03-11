#!/usr/bin/env python
"""
Test directo de la vista ListaPropiedadesView.
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

print("=== TEST DIRECTO DE LA VISTA ===")
print()

# Crear request factory
rf = RequestFactory()

# Probar diferentes casos
test_cases = [
    ("Sin parámetros", {}),
    ("Solo Propify", {'fuente_propify': 'propify'}),
    ("Solo locales", {'fuente_local': 'local'}),
    ("Solo externas", {'fuente_externa': 'externa'}),
    ("Todos", {'fuente_local': 'local', 'fuente_externa': 'externa', 'fuente_propify': 'propify'}),
]

for name, params in test_cases:
    print(f"Test: {name}")
    print(f"Parámetros: {params}")
    
    # Crear request
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    path = f'/ingestas/propiedades/?{query_string}' if query_string else '/ingestas/propiedades/'
    request = rf.get(path)
    
    # Crear vista
    view = ListaPropiedadesView()
    view.request = request
    view.kwargs = {}
    
    try:
        # Obtener propiedades usando el método interno
        print("  Llamando a _obtener_todas_propiedades()...")
        todas_propiedades = view._obtener_todas_propiedades()
        
        print(f"  Total propiedades obtenidas: {len(todas_propiedades)}")
        
        # Contar por tipo
        locales = sum(1 for p in todas_propiedades if not p.get('es_externo', False) and not p.get('es_propify', False))
        externas = sum(1 for p in todas_propiedades if p.get('es_externo', False) and not p.get('es_propify', False))
        propify = sum(1 for p in todas_propiedades if p.get('es_propify', False))
        
        print(f"  Desglose - Locales: {locales}, Externas: {externas}, Propify: {propify}")
        
        # Mostrar algunas propiedades Propify si hay
        if propify > 0:
            propify_props = [p for p in todas_propiedades if p.get('es_propify', False)][:3]
            print(f"  Primeras {len(propify_props)} propiedades Propify:")
            for i, p in enumerate(propify_props):
                print(f"    {i+1}. ID: {p.get('id')}, Tipo: {p.get('tipo_propiedad')}, "
                      f"Precio: {p.get('precio_usd')}, Lat: {p.get('lat')}, Lng: {p.get('lng')}")
        
        # Verificar que las propiedades Propify tengan el campo es_propify=True
        propify_with_flag = sum(1 for p in todas_propiedades if p.get('es_propify') == True)
        print(f"  Propiedades con es_propify=True: {propify_with_flag}")
        
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print()

print("=== TEST COMPLETADO ===")