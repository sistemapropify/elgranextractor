#!/usr/bin/env python
"""
Script para explorar todas las tablas en la base de datos propifai.
"""
import os
import sys
import django

# Configurar Django
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

django.setup()

from django.db import connections

def explore_all_tables():
    """Explora todas las tablas en la base de datos propifai."""
    try:
        connection = connections['propifai']
        with connection.cursor() as cursor:
            # Obtener todas las tablas
            cursor.execute("""
                SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """)
            tables = cursor.fetchall()
            
            print(f"Total de tablas en propifai: {len(tables)}")
            print("\nLista de tablas:")
            for schema, table, table_type in tables:
                print(f"  {schema}.{table}")
                
                # Si la tabla parece ser principal (sin underscore o con nombre simple)
                if not '_' in table or table in ['properties', 'property', 'propierty', 'listings']:
                    try:
                        # Obtener número de filas
                        cursor.execute(f"SELECT COUNT(*) FROM [{schema}].[{table}]")
                        count = cursor.fetchone()[0]
                        print(f"    - Filas: {count}")
                        
                        # Obtener algunas columnas clave
                        cursor.execute("""
                            SELECT COLUMN_NAME, DATA_TYPE
                            FROM INFORMATION_SCHEMA.COLUMNS
                            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                            ORDER BY ORDINAL_POSITION
                            LIMIT 5
                        """, (schema, table))
                        columns = cursor.fetchall()
                        print(f"    - Primeras columnas: {[c[0] for c in columns]}")
                    except:
                        pass
            
            return len(tables)
            
    except Exception as e:
        print(f"[ERROR] Error explorando tablas: {e}")
        return 0

if __name__ == "__main__":
    print("Explorando todas las tablas en base de datos 'propifai'...")
    table_count = explore_all_tables()
    print(f"\nTotal de tablas encontradas: {table_count}")