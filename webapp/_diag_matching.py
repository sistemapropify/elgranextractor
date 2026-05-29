import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from matching.engine import _fetch_properties, _PROPERTY_TYPES_CACHE, _recargar_cache_property_types
from matching.models import MatchResult
from requerimientos.models import Requerimiento
from django.db import connections

# 1. DB name
from django.conf import settings
db_name = settings.DATABASES['propifai']['NAME']
print(f"DB Name: {db_name}")

# 2. Test tables exist via propifai connection
try:
    with connections['propifai'].cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM property")
        count = cursor.fetchone()[0]
        print(f"Propiedades en DB: {count}")
        cursor.execute("SELECT COUNT(*) FROM property WHERE is_visible = 1")
        visible = cursor.fetchone()[0]
        print(f"Propiedades visibles: {visible}")
except Exception as e:
    print(f"Error querying property table: {e}")

# 3. Fetch properties via engine
props = _fetch_properties(is_active_only=True)
print(f"Propiedades cargadas por engine: {len(props)}")

if props:
    p = props[0]
    print(f"Campos: {list(p.keys())[:20]}")
    print(f"ID: {p['id']}, district_id: {p.get('district_id')}, property_type_id: {p.get('property_type_id')}, operation_type_id: {p.get('operation_type_id')}, price: {p.get('price')}, currency_id: {p.get('currency_id')}")

# 4. PropertyTypes cache
_recargar_cache_property_types()
print(f"PropertyTypes cache: {_PROPERTY_TYPES_CACHE}")

# 5. MatchResult count
mr_count = MatchResult.objects.count()
print(f"MatchResult total: {mr_count}")
if mr_count > 0:
    latest = MatchResult.objects.order_by('-ejecutado_en').first()
    print(f"Ultimo match: req_id={latest.requerimiento_id}, propiedad_id={latest.propiedad_id}, score={latest.score_total}, fecha={latest.ejecutado_en}")

# 6. Requerimientos count
req_count = Requerimiento.objects.count()
print(f"Requerimientos total: {req_count}")

# 7. Sample requerimiento
req = Requerimiento.objects.filter(tipo_propiedad__isnull=False).exclude(tipo_propiedad='no_especificado').first()
if req:
    print(f"Sample req: id={req.id}, tipo={req.tipo_propiedad}, condicion={req.condicion}, distritos={req.distritos}, presupuesto={req.presupuesto_monto} {req.presupuesto_moneda}")

# 8. Operation types
try:
    with connections['propifai'].cursor() as cursor:
        cursor.execute("SELECT id, name FROM operation_type")
        rows = cursor.fetchall()
        print(f"Operation types: {dict(rows)}")
except Exception as e:
    print(f"Error operation_types: {e}")
