import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()
from django.db import connection

# Verificar tablas en la base de datos
with connection.cursor() as cursor:
    # Para SQL Server
    cursor.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """)
    tables = cursor.fetchall()
    
    print(f'Tablas encontradas ({len(tables)}):')
    for schema, table in tables:
        print(f'  {schema}.{table}')
    
    # Buscar tablas relacionadas con propifai
    print('\nTablas relacionadas con propifai:')
    for schema, table in tables:
        if 'propifai' in table.lower() or 'propiedad' in table.lower():
            print(f'  {schema}.{table}')
            
    # Verificar estructura de una tabla de propiedades
    print('\nEstructura de posibles tablas de propiedades:')
    prop_tables = [t for s, t in tables if 'propiedad' in t.lower()]
    for table in prop_tables[:3]:  # Revisar solo las primeras 3
        try:
            cursor.execute(f"""
                SELECT COLUMN_NAME, DATA_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = '{table}'
                ORDER BY ORDINAL_POSITION
            """)
            columns = cursor.fetchall()
            print(f'\n  Tabla: {table} ({len(columns)} columnas)')
            for col_name, col_type in columns[:10]:  # Mostrar primeras 10 columnas
                print(f'    {col_name}: {col_type}')
            if len(columns) > 10:
                print(f'    ... y {len(columns)-10} columnas más')
        except Exception as e:
            print(f'  Error al leer tabla {table}: {e}')