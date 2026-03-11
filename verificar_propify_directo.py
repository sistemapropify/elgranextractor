#!/usr/bin/env python
"""
Verificación directa de propiedades Propify desde la base de datos.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty

print("=== VERIFICACIÓN DIRECTA DE PROPIEDADES PROPIFY ===\n")

# 1. Verificar conexión a la base de datos
try:
    count = PropifaiProperty.objects.count()
    print(f"1. Conteo total de propiedades en tabla Propifai: {count}")
    
    # Obtener algunas propiedades
    propiedades = PropifaiProperty.objects.all()[:5]
    print(f"2. Primeras 5 propiedades:")
    for i, prop in enumerate(propiedades, 1):
        print(f"   {i}. ID: {prop.id}, Código: {prop.code}, Departamento: {prop.department}")
        print(f"      Coordenadas: {prop.coordinates}")
        print(f"      Latitud: {prop.latitude}, Longitud: {prop.longitude}")
        print(f"      Precio: {prop.price}, Habitaciones: {prop.bedrooms}")
    
    # Verificar coordenadas
    print(f"\n3. Propiedades con coordenadas válidas:")
    props_con_coordenadas = PropifaiProperty.objects.exclude(coordinates__isnull=True).exclude(coordinates='')[:10]
    for prop in props_con_coordenadas:
        print(f"   - ID: {prop.id}, Coordenadas: {prop.coordinates}, Lat: {prop.latitude}, Lng: {prop.longitude}")
    
    # Verificar si hay propiedades sin coordenadas
    props_sin_coordenadas = PropifaiProperty.objects.filter(coordinates__isnull=True) | PropifaiProperty.objects.filter(coordinates='')
    print(f"\n4. Propiedades sin coordenadas: {props_sin_coordenadas.count()}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

# 2. Verificar la vista
print("\n=== VERIFICACIÓN DE LA VISTA ===\n")

from django.test import RequestFactory
from ingestas.views import ListaPropiedadesView

factory = RequestFactory()

# Test 1: Sin filtros
print("Test 1: Sin filtros (debería incluir Propify)")
request = factory.get('/ingestas/propiedades/', data={})
view = ListaPropiedadesView()
view.request = request

try:
    todas_propiedades = view._obtener_todas_propiedades()
    print(f"   Total propiedades obtenidas: {len(todas_propiedades)}")
    
    # Contar por tipo
    locales = sum(1 for p in todas_propiedades if not p.get('es_externo') and not p.get('es_propify'))
    externas = sum(1 for p in todas_propiedades if p.get('es_externo') and not p.get('es_propify'))
    propify = sum(1 for p in todas_propiedades if p.get('es_propify'))
    
    print(f"   Locales: {locales}, Externas: {externas}, Propify: {propify}")
    
    # Mostrar algunas propiedades Propify
    print(f"\n   Primeras 3 propiedades Propify:")
    propify_props = [p for p in todas_propiedades if p.get('es_propify')][:3]
    for i, prop in enumerate(propify_props, 1):
        print(f"   {i}. ID: {prop.get('id')}, Código: {prop.get('codigo')}")
        print(f"      Departamento: {prop.get('departamento')}, Precio: {prop.get('precio_usd')}")
        print(f"      Coordenadas: Lat={prop.get('lat')}, Lng={prop.get('lng')}")
        print(f"      ¿Tiene coordenadas?: {'Sí' if prop.get('lat') and prop.get('lng') else 'No'}")
    
except Exception as e:
    print(f"ERROR en vista: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Solo Propify
print("\nTest 2: Solo Propify marcado")
request = factory.get('/ingestas/propiedades/', data={'fuente_propify': 'propify'})
view = ListaPropiedadesView()
view.request = request

try:
    todas_propiedades = view._obtener_todas_propiedades()
    print(f"   Total propiedades obtenidas: {len(todas_propiedades)}")
    
    # Contar por tipo
    locales = sum(1 for p in todas_propiedades if not p.get('es_externo') and not p.get('es_propify'))
    externas = sum(1 for p in todas_propiedades if p.get('es_externo') and not p.get('es_propify'))
    propify = sum(1 for p in todas_propiedades if p.get('es_propify'))
    
    print(f"   Locales: {locales}, Externas: {externas}, Propify: {propify}")
    
except Exception as e:
    print(f"ERROR en vista: {e}")