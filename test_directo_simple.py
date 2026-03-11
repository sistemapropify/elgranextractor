#!/usr/bin/env python3
"""
Test directo y simple
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

print("=== TEST DIRECTO SIMPLE ===")

# Crear request
factory = RequestFactory()
request = factory.get('/ingestas/propiedades/', {'fuente_propify': 'propify'})

# Crear vista
view = ListaPropiedadesView()
view.request = request

print("1. Probando solo la parte de Propifai...")
try:
    from propifai.models import PropifaiProperty
    print("   - Modelo importado OK")
    
    count = PropifaiProperty.objects.count()
    print(f"   - Count en BD: {count}")
    
    props = list(PropifaiProperty.objects.all()[:5])
    print(f"   - Primeras {len(props)} propiedades obtenidas")
    
    for i, prop in enumerate(props):
        print(f"   - Prop {i+1}: ID={prop.id}, code={prop.code}")
        
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n2. Probando _convertir_propiedad_propifai_a_dict...")
try:
    if 'props' in locals() and props:
        prop_dict = view._convertir_propiedad_propifai_a_dict(props[0])
        print(f"   - Conversión exitosa")
        print(f"   - es_propify: {prop_dict.get('es_propify')}")
        print(f"   - es_externo: {prop_dict.get('es_externo')}")
        print(f"   - lat/lng: {prop_dict.get('lat')}, {prop_dict.get('lng')}")
    else:
        print("   - No hay propiedades para probar")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n=== TEST COMPLETADO ===")