import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()
from matching.engine import _fetch_properties
props = _fetch_properties(is_active_only=True)
print(f"Propiedades: {len(props)}")
if props:
    p = props[0]
    print(f"property_type_name: {p.get('property_type_name')}")
    print(f"operation_type_name: {p.get('operation_type_name')}")
    print(f"property_type_id: {p.get('property_type_id')}")
    print(f"operation_type_id: {p.get('operation_type_id')}")
    # Verificar si vienen null
    nulos = sum(1 for pp in props if not pp.get('property_type_name'))
    print(f"Property type name NULL: {nulos}")
    nulos2 = sum(1 for pp in props if not pp.get('operation_type_name'))
    print(f"Operation type name NULL: {nulos2}")
