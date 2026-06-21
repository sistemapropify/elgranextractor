import os, sys
sys.path.insert(0, 'webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
import django
django.setup()
from django.db import connections

# 1. Buscar columna de moneda en properties
cursor = connections['propifai'].cursor()
cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'properties' AND (COLUMN_NAME LIKE '%currency%' OR COLUMN_NAME LIKE '%moneda%' OR COLUMN_NAME LIKE '%price_unit%' OR COLUMN_NAME LIKE '%coin%')")
cols = cursor.fetchall()
print('Columnas moneda:', cols)

# 2. Ver precio de PROP000048
cursor.execute("SELECT code, price, district, property_type_id, operation_type_id FROM properties WHERE code = 'PROP000048'")
row = cursor.fetchone()
print('PROP000048:', row)

# 3. Ver algunos precios de ejemplo
cursor.execute("SELECT TOP 10 code, price, district FROM properties WHERE price IS NOT NULL AND is_active = 1")
rows = cursor.fetchall()
print('Ejemplos precios:')
for r in rows:
    print(f'  {r[0]}: price={r[1]}, district={r[2]}')

# 4. Ver requerimiento 20263
from requerimientos.models import Requerimiento
r = Requerimiento.objects.get(id=20263)
print(f'Req 20263: presupuesto={r.presupuesto_monto} {r.presupuesto_moneda}, tipo={r.tipo_propiedad}, distritos={r.distritos}, condicion={r.condicion}')
