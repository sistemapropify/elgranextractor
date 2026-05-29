import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()
from matching.engine import _recargar_cache_property_types, _PROPERTY_TYPES_CACHE, _PROPERTY_TYPES_NAME_TO_ID, _get_property_type_id
from requerimientos.models import Requerimiento
from django.db import connections

_recargar_cache_property_types()
print(f"PropertyTypes: {_PROPERTY_TYPES_CACHE}")
print(f"NameToID: {_PROPERTY_TYPES_NAME_TO_ID}")

req = Requerimiento.objects.get(id=24304)
print(f"tipo_propiedad raw: '{req.tipo_propiedad}'")
print(f"condicion raw: '{req.condicion}'")
print(f"distritos raw: '{req.distritos}'")
print(f"presupuesto: {req.presupuesto_monto} {req.presupuesto_moneda}")

# Resolve
tipo_id = _get_property_type_id(req.tipo_propiedad)
print(f"Tipo ID resuelto: {tipo_id}")

# Check property types in DB
with connections['propifai'].cursor() as cursor:
    cursor.execute("SELECT id, name FROM property_type WHERE is_active = 1")
    rows = cursor.fetchall()
    print(f"DB property_types: {dict(rows)}")
    
    cursor.execute("SELECT id, name FROM operation_type")
    rows = cursor.fetchall()
    print(f"DB operation_types: {dict(rows)}")
