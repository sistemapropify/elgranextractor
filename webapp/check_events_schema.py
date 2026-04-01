#!/usr/bin/env python
"""
Script para inspeccionar la estructura de las tablas events y event_types.
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.db import connections

def inspect_table(table_name):
    print(f"\n=== Tabla: {table_name} ===")
    connection = connections['propifai']
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=%s
                ORDER BY ORDINAL_POSITION
            """, [table_name])
            rows = cursor.fetchall()
            if not rows:
                print("  No se encontraron columnas.")
                return
            for col, dtype, nullable, max_len in rows:
                nullable_str = 'NULL' if nullable == 'YES' else 'NOT NULL'
                length_str = f'({max_len})' if max_len else ''
                print(f"  {col}: {dtype}{length_str} {nullable_str}")
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == '__main__':
    inspect_table('events')
    inspect_table('event_types')
    inspect_table('property_statuses')
    inspect_table('property_types')
    inspect_table('users')
    inspect_table('crm_leads')
    inspect_table('proposals')