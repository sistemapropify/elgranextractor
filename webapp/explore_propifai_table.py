#!/usr/bin/env python
"""
Script para explorar la tabla 'propierty' en la base de datos propifai.
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

def explore_property_table():
    """Explora la tabla de propiedades en la base de datos propifai."""
    try:
        connection = connections['propifai']
        with connection.cursor() as cursor:
            # Buscar tablas que contengan 'property' o 'propierty'
            cursor.execute("""
                SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                AND (TABLE_NAME LIKE '%property%' OR TABLE_NAME LIKE '%propierty%')
                ORDER BY TABLE_SCHEMA, TABLE_NAME
            """)
            tables = cursor.fetchall()
            
            print("Tablas encontradas que contienen 'property' o 'propierty':")
            for schema, table, table_type in tables:
                print(f"  {schema}.{table} ({table_type})")
                
                try:
                    # Obtener columnas de la tabla
                    cursor.execute("""
                        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                        ORDER BY ORDINAL_POSITION
                    """, (schema, table))
                    columns = cursor.fetchall()
                    
                    print(f"    Columnas ({len(columns)}):")
                    for col_name, data_type, is_nullable, char_max_len in columns:
                        type_info = data_type
                        if char_max_len:
                            type_info += f"({char_max_len})"
                        print(f"      - {col_name}: {type_info}, nullable: {is_nullable}")
                    
                    # Obtener algunas filas de ejemplo
                    cursor.execute(f"SELECT TOP 5 * FROM [{schema}].[{table}]")
                    rows = cursor.fetchall()
                    if rows:
                        print(f"    Primeras 5 filas:")
                        for i, row in enumerate(rows):
                            print(f"      Fila {i+1}: {row}")
                except Exception as e:
                    print(f"    Error al obtener detalles: {e}")
            
            return len(tables)
            
    except Exception as e:
        print(f"[ERROR] Error explorando tabla: {e}")
        return 0

if __name__ == "__main__":
    print("Explorando tabla de propiedades en base de datos 'propifai'...")
    table_count = explore_property_table()
    print(f"\nTotal de tablas encontradas: {table_count}")