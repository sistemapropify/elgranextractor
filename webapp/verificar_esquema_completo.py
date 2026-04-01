#!/usr/bin/env python
"""
Script para verificar el esquema completo de la base de datos.
"""

import os
import sys
import django
from django.db import connection

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')
django.setup()

def main():
    print("=== TABLAS EN LA BASE DE DATOS ===")
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        tables = cursor.fetchall()
        for schema, table in tables:
            print(f"  {schema}.{table}")
    
    print("\n=== TABLAS QUE CONTIENEN 'propiedadraw' ===")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME LIKE '%propiedadraw%'
        """)
        tables = cursor.fetchall()
        for schema, table in tables:
            print(f"  {schema}.{table}")
            
            # Listar columnas de esta tabla
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
            """, [schema, table])
            columns = cursor.fetchall()
            for col_name, data_type, nullable in columns:
                print(f"    - {col_name} ({data_type}, nullable: {nullable})")
    
    print("\n=== VERIFICACIÓN ESPECÍFICA DE COLUMNAS ===")
    target_tables = ['ingestas_propiedadraw', 'propiedadraw', 'ingestas_propiedadraws']
    for table in target_tables:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = ?
            """, [table])
            if cursor.fetchone()[0] == 0:
                print(f"  Tabla '{table}' NO EXISTE.")
                continue
            
            print(f"  Tabla '{table}':")
            for col in ['condicion', 'propiedad_verificada']:
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
                """, [table, col])
                exists = cursor.fetchone()[0] > 0
                print(f"    - {col}: {'EXISTE' if exists else 'NO EXISTE'}")
    
    print("\n=== CONSULTA DE DATOS DE EJEMPLO ===")
    # Intentar seleccionar algunas filas
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT TOP 3 id, condicion, propiedad_verificada FROM ingestas_propiedadraw")
            rows = cursor.fetchall()
            if rows:
                print("  Primeros 3 registros:")
                for row in rows:
                    print(f"    {row}")
            else:
                print("  No hay registros en la tabla.")
    except Exception as e:
        print(f"  Error al consultar datos: {e}")

if __name__ == '__main__':
    main()