import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection

c = IntelligenceCollection.objects.get(name='propiedades_propify')
print(f'source_sql: {c.source_sql}')
print(f'table_name: {c.table_name}')
print(f'database_alias: {getattr(c, "database_alias", "NO FIELD")}')
print(f'embedding_fields: {c.embedding_fields}')
print(f'display_fields count: {len(c.display_fields)}')

# Ver si existe la tabla properties en otra base de datos
from django.db import connections
conn = connections['default']
with conn.cursor() as cursor:
    cursor.execute("SELECT DB_NAME()")
    db_name = cursor.fetchone()[0]
    print(f'\nDatabase actual: {db_name}')
    
    # Buscar properties en cualquier esquema
    cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'properties'")
    results = cursor.fetchall()
    print(f'Tablas llamadas properties: {results}')
    
    # Buscar tablas de distritos
    cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%district%' OR TABLE_NAME LIKE '%distrito%'")
    results = cursor.fetchall()
    print(f'Tablas de distritos: {results}')
    
    # Ver columnas de la tabla properties si existe
    if results:
        schema = results[0][0]
        cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='{schema}' AND TABLE_NAME='properties'")
        cols = [r[0] for r in cursor.fetchall()]
        print(f'Columnas de properties: {cols}')
