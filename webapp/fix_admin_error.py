#!/usr/bin/env python
"""
Script para diagnosticar y corregir el error del admin de Django.
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
    print("=== DIAGNÓSTICO ERROR ADMIN DJANGO ===\n")
    
    # 1. Verificar tabla
    table_name = 'ingestas_propiedadraw'
    print(f"1. Buscando tabla '{table_name}'...")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = ?
        """, [table_name])
        result = cursor.fetchone()
        if result:
            schema, table = result
            print(f"   ✓ Tabla encontrada: {schema}.{table}")
        else:
            print(f"   ✗ Tabla NO encontrada. Buscando variantes...")
            cursor.execute("""
                SELECT TABLE_SCHEMA, TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME LIKE '%propiedadraw%'
            """)
            tables = cursor.fetchall()
            for sch, tbl in tables:
                print(f"      - {sch}.{tbl}")
            return
    
    # 2. Verificar columnas específicas
    print("\n2. Verificando columnas requeridas...")
    required_columns = ['condicion', 'propiedad_verificada']
    for col in required_columns:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
            """, [table_name, col])
            exists = cursor.fetchone()[0] > 0
            if exists:
                print(f"   ✓ Columna '{col}' EXISTE")
            else:
                print(f"   ✗ Columna '{col}' NO EXISTE")
    
    # 3. Intentar agregar columnas faltantes
    print("\n3. Agregando columnas faltantes...")
    for col in required_columns:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
            """, [table_name, col])
            if cursor.fetchone()[0] > 0:
                continue
            
            print(f"   Agregando columna '{col}'...")
            try:
                if col == 'condicion':
                    cursor.execute(f"""
                        ALTER TABLE {table_name}
                        ADD {col} NVARCHAR(20) NULL
                    """)
                elif col == 'propiedad_verificada':
                    cursor.execute(f"""
                        ALTER TABLE {table_name}
                        ADD {col} BIT NULL
                    """)
                print(f"   ✓ Columna '{col}' agregada.")
            except Exception as e:
                print(f"   ✗ Error al agregar '{col}': {e}")
    
    # 4. Verificar tipos de datos
    print("\n4. Verificando tipos de datos...")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
        """, [table_name])
        columns = cursor.fetchall()
        print(f"   Total columnas: {len(columns)}")
        for col_name, data_type, nullable in columns:
            print(f"      {col_name}: {data_type} (nullable: {nullable})")
    
    # 5. Simular consulta del admin
    print("\n5. Simulando consulta SELECT del admin...")
    try:
        with connection.cursor() as cursor:
            # Consulta similar a la que Django ejecuta para listar objetos
            cursor.execute(f"SELECT TOP 1 id, condicion, propiedad_verificada FROM {table_name}")
            print(f"   ✓ Consulta SELECT ejecutada exitosamente.")
            row = cursor.fetchone()
            if row:
                print(f"   Datos de ejemplo: {row}")
            else:
                print(f"   Tabla vacía o sin registros.")
    except Exception as e:
        print(f"   ✗ Error en consulta SELECT: {e}")
        # Mostrar error detallado
        import traceback
        traceback.print_exc()
    
    # 6. Verificar si hay registros
    print("\n6. Conteo de registros...")
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"   Total registros: {count}")
    except Exception as e:
        print(f"   ✗ Error al contar: {e}")
    
    print("\n=== DIAGNÓSTICO COMPLETADO ===")
    print("\nRecomendaciones:")
    print("1. Si las columnas fueron agregadas, reinicia el servidor Django.")
    print("2. Si el error persiste, verifica que el modelo PropiedadRaw tenga los campos definidos correctamente.")
    print("3. Revisa las migraciones pendientes con: python manage.py showmigrations ingestas")

if __name__ == '__main__':
    main()