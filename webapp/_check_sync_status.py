"""
Script para verificar estado de colecciones y sincronizar propiedades_propify.
"""
import sys
import os
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument
from django.db import connections

# Ver colecciones
cols = IntelligenceCollection.objects.all()
print('=== COLECCIONES ===')
for c in cols:
    doc_count = IntelligenceDocument.objects.filter(collection=c).count()
    print(f'  {c.name}: {doc_count} docs, table={c.table_name}, db_alias={c.database_alias}')

# Ver tabla properties en propifai
conn = connections['propifai']
with conn.cursor() as cursor:
    cursor.execute('SELECT COUNT(*) FROM properties')
    count = cursor.fetchone()[0]
    print(f'\n=== Tabla properties (propifai) ===')
    print(f'  Total registros: {count}')
    
    cursor.execute('SELECT TOP 3 id, title, price, currency_id, district, urbanization FROM properties')
    columns = [col[0] for col in cursor.description]
    for row in cursor.fetchall():
        print(f'  {dict(zip(columns, row))}')

print('\n=== HECHO ===')
