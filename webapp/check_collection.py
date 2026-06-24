"""
Check collection configuration.
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
import django
django.setup()

from intelligence.models import IntelligenceCollection

c = IntelligenceCollection.objects.get(name='propiedadespropify')
print('=== COLLECTION CONFIG ===')
for field in c._meta.get_fields():
    if hasattr(c, field.name):
        val = getattr(c, field.name)
        if not callable(val) and not str(type(val)).startswith('<django'):
            print(f'{field.name}: {val}')

# Check what fields the source table/view has
print('\n=== CHECKING SOURCE TABLE ===')
from django.db import connections
db_alias = getattr(c, 'database_alias', None) or 'default'
conn = connections[db_alias]
source_table = getattr(c, 'source_table', 'vwd_propiedades_propify_listado')
print(f'Looking for table: {source_table}')

try:
    with conn.cursor() as cursor:
        cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = %s", (source_table,))
        row = cursor.fetchone()
        if row:
            print(f'Found: {row[0]}.{row[1]}')
            cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{source_table}'")
            cols = [r[0] for r in cursor.fetchall()]
            print(f'Columns ({len(cols)}):')
            for col in cols:
                print(f'  - {col}')
        else:
            print(f'Table not found. Searching...')
            cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%prop%' ORDER BY TABLE_NAME")
            for r in cursor.fetchall():
                print(f'  Found: {r[0]}.{r[1]}')
except Exception as e:
    print(f'Error: {e}')
