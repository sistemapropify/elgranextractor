import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'ingestas_propiedadraw'
        ORDER BY ORDINAL_POSITION
    """)
    columns = cursor.fetchall()
    print(f'Total columnas: {len(columns)}')
    for col in columns:
        print(f'{col[0]} ({col[1]}) - Nullable: {col[2]}')