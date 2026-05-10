"""
Script para aplicar la migración 0015 manualmente (ALTER TABLE ADD COLUMN)
y verificar el estado de las colecciones.
"""
import sys
import os
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from django.db import connections

conn = connections['default']
cursor = conn.cursor()

# Verificar si la columna ya existe
cursor.execute("""
    SELECT COUNT(*) FROM information_schema.columns 
    WHERE table_name = 'intelligence_collections' 
    AND column_name = 'database_alias'
""")
exists = cursor.fetchone()[0]

if not exists:
    print('Agregando columna database_alias a intelligence_collections...')
    cursor.execute("""
        ALTER TABLE intelligence_collections 
        ADD database_alias NVARCHAR(50) NOT NULL DEFAULT 'default'
    """)
    print('Columna agregada exitosamente.')
else:
    print('La columna database_alias ya existe.')

# Ahora verificar colecciones
print('\n=== COLECCIONES ===')
cursor.execute('SELECT id, name, table_name, database_alias, last_sync_count FROM intelligence_collections ORDER BY name')
columns = [col[0] for col in cursor.description]
for row in cursor.fetchall():
    row_dict = dict(zip(columns, row))
    print(f'  {row_dict["name"]}: table={row_dict["table_name"]}, db_alias={row_dict["database_alias"]}, docs={row_dict["last_sync_count"]}')

# Ver documentos
cursor.execute('SELECT COUNT(*) FROM intelligence_documents')
doc_count = cursor.fetchone()[0]
print(f'\nTotal documentos en intelligence_documents: {doc_count}')

cursor.close()

# Ver tabla properties en propifai
conn2 = connections['propifai']
cursor2 = conn2.cursor()
cursor2.execute('SELECT COUNT(*) FROM properties')
count = cursor2.fetchone()[0]
print(f'\n=== Tabla properties (propifai) ===')
print(f'  Total registros: {count}')

cursor2.execute('SELECT TOP 3 id, title, price, currency_id, district, urbanization FROM properties')
columns2 = [col[0] for col in cursor2.description]
for row in cursor2.fetchall():
    print(f'  {dict(zip(columns2, row))}')
cursor2.close()

print('\n=== HECHO ===')
