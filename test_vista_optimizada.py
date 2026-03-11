#!/usr/bin/env python
"""
Test rápido de la vista optimizada.
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

print("=== TEST DE VISTA OPTIMIZADA ===")
print()

# Crear request factory
rf = RequestFactory()

# Probar solo Propify
print("Test 1: Solo Propify seleccionado")
request = rf.get('/ingestas/propiedades/?fuente_propify=propify')

view = ListaPropiedadesView()
view.request = request
view.kwargs = {}

try:
    print("Obteniendo propiedades...")
    todas_propiedades = view._obtener_todas_propiedades()
    
    print(f"Total propiedades: {len(todas_propiedades)}")
    
    # Contar Propify
    propify_count = sum(1 for p in todas_propiedades if p.get('es_propify', False))
    print(f"Propiedades Propify: {propify_count}")
    
    if propify_count > 0:
        print(f"\nPrimeras 2 propiedades Propify:")
        for i, p in enumerate(todas_propiedades[:2]):
            print(f"  {i+1}. ID: {p.get('id')}, Tipo: {p.get('tipo_propiedad')}, "
                  f"Precio: {p.get('precio_usd')}, Lat: {p.get('lat')}, Lng: {p.get('lng')}")
    else:
        print("\n¡ERROR: No se encontraron propiedades Propify!")
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
print("Test 2: Todos los checkboxes seleccionados (default)")
request2 = rf.get('/ingestas/propiedades/')

view2 = ListaPropiedadesView()
view2.request = request2
view2.kwargs = {}

try:
    print("Obteniendo propiedades...")
    todas_propiedades2 = view2._obtener_todas_propiedades()
    
    print(f"Total propiedades: {len(todas_propiedades2)}")
    
    # Contar por tipo
    locales = sum(1 for p in todas_propiedades2 if not p.get('es_externo', False) and not p.get('es_propify', False))
    externas = sum(1 for p in todas_propiedades2 if p.get('es_externo', False) and not p.get('es_propify', False))
    propify = sum(1 for p in todas_propiedades2 if p.get('es_propify', False))
    
    print(f"Desglose - Locales: {locales}, Externas: {externas}, Propify: {propify}")
    
except Exception as e:
    print(f"ERROR: {e}")

print()
print("=== TEST COMPLETADO ===")