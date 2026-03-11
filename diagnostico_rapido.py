#!/usr/bin/env python
"""
Diagnóstico rápido del problema de Propify.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty
from ingestas.views import ListaPropiedadesView
from django.test import RequestFactory

print("=== DIAGNÓSTICO RÁPIDO DE PROPIEDADES PROPIY ===")
print()

# 1. Verificar base de datos directamente
print("1. Verificando base de datos Propifai...")
try:
    count = PropifaiProperty.objects.using('propifai').count()
    print(f"   Total propiedades en DB Propifai: {count}")
    
    # Mostrar algunas propiedades
    props = PropifaiProperty.objects.using('propifai').all()[:3]
    for i, p in enumerate(props):
        print(f"   Propiedad {i+1}: ID={p.id}, Tipo={p.tipo_propiedad}, "
              f"Precio={p.price}, Lat={p.latitude}, Lng={p.longitude}")
except Exception as e:
    print(f"   ERROR al acceder a DB Propifai: {e}")

print()

# 2. Verificar la vista con diferentes parámetros
print("2. Probando la vista ListaPropiedadesView...")

# Crear request factory
rf = RequestFactory()

# Probar con diferentes combinaciones de parámetros
test_cases = [
    ("Sin parámetros (default)", {}),
    ("Solo Propify", {'fuente_propify': 'propify'}),
    ("Solo locales", {'fuente_local': 'local'}),
    ("Solo externas", {'fuente_externa': 'externa'}),
    ("Propify + locales", {'fuente_propify': 'propify', 'fuente_local': 'local'}),
]

for name, params in test_cases:
    print(f"   Caso: {name}")
    
    # Crear request
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    path = f'/ingestas/propiedades/?{query_string}' if query_string else '/ingestas/propiedades/'
    request = rf.get(path)
    
    # Crear vista
    view = ListaPropiedadesView()
    view.request = request
    view.kwargs = {}
    
    try:
        # Obtener propiedades
        todas_propiedades = view._obtener_todas_propiedades()
        
        # Contar por tipo
        locales = sum(1 for p in todas_propiedades if not p.get('es_externo', False) and not p.get('es_propify', False))
        externas = sum(1 for p in todas_propiedades if p.get('es_externo', False) and not p.get('es_propify', False))
        propify = sum(1 for p in todas_propiedades if p.get('es_propify', False))
        
        print(f"     Total: {len(todas_propiedades)}, "
              f"Locales: {locales}, Externas: {externas}, Propify: {propify}")
        
        # Mostrar primeros IDs si hay Propify
        if propify > 0:
            propify_ids = [p.get('id_externo', p.get('id', 'N/A')) for p in todas_propiedades if p.get('es_propify', False)][:3]
            print(f"     IDs Propify (primeros 3): {propify_ids}")
    except Exception as e:
        print(f"     ERROR: {e}")

print()

# 3. Verificar el método _convertir_propiedad_propifai_a_dict
print("3. Verificando conversión de propiedades Propifai...")
try:
    # Obtener una propiedad de ejemplo
    prop = PropifaiProperty.objects.using('propifai').first()
    if prop:
        view = ListaPropiedadesView()
        prop_dict = view._convertir_propiedad_propifai_a_dict(prop)
        print(f"   Propiedad convertida: ID={prop_dict.get('id')}, "
              f"es_externo={prop_dict.get('es_externo')}, "
              f"es_propify={prop_dict.get('es_propify')}")
        print(f"   Campos importantes: lat={prop_dict.get('lat')}, lng={prop_dict.get('lng')}")
    else:
        print("   No hay propiedades en la base de datos")
except Exception as e:
    print(f"   ERROR en conversión: {e}")

print()
print("=== DIAGNÓSTICO COMPLETADO ===")