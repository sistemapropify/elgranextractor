import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
import django
django.setup()
from django.db import connections

cursor = connections['propifai'].cursor()

# Ver valores de currency_id
cursor.execute("SELECT DISTINCT currency_id FROM properties WHERE currency_id IS NOT NULL")
rows = cursor.fetchall()
print('Valores de currency_id:', rows)

# Ver currency_id de PROP000048
cursor.execute("SELECT code, price, currency_id FROM properties WHERE code = 'PROP000048'")
row = cursor.fetchone()
print('PROP000048 currency:', row)

# Ver tabla currency
cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME LIKE '%currency%'")
cols = cursor.fetchall()
print('Columnas en tablas currency:', cols)

# Ver algunos precios con currency_id
cursor.execute("SELECT TOP 10 code, price, currency_id FROM properties WHERE price IS NOT NULL AND is_active = 1 ORDER BY price DESC")
rows = cursor.fetchall()
print('Precios con currency:')
for r in rows:
    print(f'  {r[0]}: price={r[1]}, currency_id={r[2]}')

# Ver tabla currencies
cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'currencies'")
cols = cursor.fetchall()
print('Columnas de currencies:', cols)

# Ver contenido de currencies
cursor.execute("SELECT * FROM currencies")
rows = cursor.fetchall()
print('Contenido de currencies:', rows)
