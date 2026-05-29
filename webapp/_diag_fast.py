import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from matching.engine import _fetch_properties, _recargar_cache_property_types, _PROPERTY_TYPES_CACHE

# 1. Fetch properties
props = _fetch_properties(is_active_only=True)
print(f"Propiedades cargadas: {len(props)}")
if props:
    p = props[0]
    print(f"district_id={p.get('district_id')}, property_type_id={p.get('property_type_id')}, operation_type_id={p.get('operation_type_id')}, currency_id={p.get('currency_id')}, price={p.get('price')}")

# 2. PropertyTypes
_recargar_cache_property_types()
print(f"PropertyTypes cache: {_PROPERTY_TYPES_CACHE}")
