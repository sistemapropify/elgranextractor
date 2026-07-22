import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
os.environ.setdefault('PROPIFAI_DB_NAME', 'dbpropify_be')
import django; django.setup()
from django.db import connections

conn = connections['propifai']
with conn.cursor() as c:
    c.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'event' ORDER BY ORDINAL_POSITION")
    cols = c.fetchall()
    print("Columnas reales de dbo.event en dbpropify_be:")
    for r in cols:
        print(f"  {r[0]:30s} {r[1]}")
