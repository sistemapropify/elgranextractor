#!/usr/bin/env python
"""
Verificar si el campo es_propify está establecido correctamente en las propiedades.
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

print("=== VERIFICACIÓN DEL CAMPO es_propify ===\n")

factory = RequestFactory()

# Test: Solo Propify marcado
request = factory.get('/ingestas/propiedades/', data={'fuente_propify': 'propify'})
view = ListaPropiedadesView()
view.setup(request)

# Obtener propiedades
todas_propiedades = view._obtener_todas_propiedades()

print(f"1. Total propiedades obtenidas: {len(todas_propiedades)}")

# Verificar campos en las propiedades
if todas_propiedades:
    print(f"\n2. Verificando campos en las primeras 3 propiedades:")
    
    for i, prop in enumerate(todas_propiedades[:3], 1):
        print(f"\n   Propiedad {i}:")
        print(f"   - ID: {prop.get('id')}")
        print(f"   - es_externo: {prop.get('es_externo')}")
        print(f"   - es_propify: {prop.get('es_propify')}")
        print(f"   - lat: {prop.get('lat')}")
        print(f"   - lng: {prop.get('lng')}")
        print(f"   - codigo: {prop.get('codigo')}")
        print(f"   - departamento: {prop.get('departamento')}")
        
        # Verificar todos los campos disponibles
        print(f"   - Todos los campos: {list(prop.keys())}")
    
    # Verificar cuántas propiedades tienen es_propify=True
    count_es_propify = sum(1 for p in todas_propiedades if p.get('es_propify'))
    print(f"\n3. Propiedades con es_propify=True: {count_es_propify} de {len(todas_propiedades)}")
    
    # Verificar cuántas propiedades tienen coordenadas
    count_con_coordenadas = sum(1 for p in todas_propiedades if p.get('lat') and p.get('lng'))
    print(f"4. Propiedades con coordenadas (lat y lng): {count_con_coordenadas} de {len(todas_propiedades)}")
    
    # Verificar si hay propiedades sin es_propify
    props_sin_es_propify = [p for p in todas_propiedades if not p.get('es_propify')]
    if props_sin_es_propify:
        print(f"\n5. ¡ADVERTENCIA! Hay {len(props_sin_es_propify)} propiedades sin es_propify")
        print(f"   Primera propiedad sin es_propify: ID={props_sin_es_propify[0].get('id')}, campos={list(props_sin_es_propify[0].keys())}")
    
    # Verificar el método _convertir_propiedad_propifai_a_dict
    print(f"\n6. Probando _convertir_propiedad_propifai_a_dict directamente:")
    try:
        from propifai.models import PropifaiProperty
        propifai_prop = PropifaiProperty.objects.first()
        if propifai_prop:
            prop_dict = view._convertir_propiedad_propifai_a_dict(propifai_prop)
            print(f"   - Propiedad convertida: ID={prop_dict.get('id')}, es_propify={prop_dict.get('es_propify')}")
            print(f"   - Campos en diccionario: {list(prop_dict.keys())}")
    except Exception as e:
        print(f"   ERROR: {e}")