#!/usr/bin/env python
"""
Script para agregar manualmente las columnas condicion y propiedad_verificada a la tabla PropiedadRaw.
"""

import os
import sys
import django
from django.db import connection

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')
django.setup()

def column_exists(table_name, column_name):
    """Verifica si una columna existe en la tabla."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
        """, [table_name, column_name])
        return cursor.fetchone()[0] > 0

def main():
    table_name = 'ingestas_propiedadraw'
    
    print(f"Verificando tabla: {table_name}")
    
    # Verificar si la tabla existe
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = ?
        """, [table_name])
        if cursor.fetchone()[0] == 0:
            print(f"Error: La tabla {table_name} no existe.")
            return
    
    # Columna condicion
    if column_exists(table_name, 'condicion'):
        print("✓ Columna 'condicion' ya existe.")
    else:
        print("Agregando columna 'condicion'...")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    ALTER TABLE {table_name}
                    ADD condicion NVARCHAR(20) NULL
                """)
            print("✓ Columna 'condicion' agregada.")
        except Exception as e:
            print(f"✗ Error al agregar 'condicion': {e}")
    
    # Columna propiedad_verificada
    if column_exists(table_name, 'propiedad_verificada'):
        print("✓ Columna 'propiedad_verificada' ya existe.")
    else:
        print("Agregando columna 'propiedad_verificada'...")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    ALTER TABLE {table_name}
                    ADD propiedad_verificada BIT NULL
                """)
            print("✓ Columna 'propiedad_verificada' agregada.")
        except Exception as e:
            print(f"✗ Error al agregar 'propiedad_verificada': {e}")
    
    # Actualizar valores por defecto si es necesario
    print("\nActualizando valores por defecto...")
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"""
                UPDATE {table_name}
                SET condicion = 'no_especificado'
                WHERE condicion IS NULL
            """)
            updated = cursor.rowcount
            print(f"✓ {updated} registros actualizados con condicion='no_especificado'.")
    except Exception as e:
        print(f"✗ Error al actualizar condicion: {e}")
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"""
                UPDATE {table_name}
                SET propiedad_verificada = 0
                WHERE propiedad_verificada IS NULL
            """)
            updated = cursor.rowcount
            print(f"✓ {updated} registros actualizados con propiedad_verificada=0.")
    except Exception as e:
        print(f"✗ Error al actualizar propiedad_verificada: {e}")
    
    print("\nVerificación final:")
    for col in ['condicion', 'propiedad_verificada']:
        exists = column_exists(table_name, col)
        print(f"  {col}: {'EXISTE' if exists else 'NO EXISTE'}")

if __name__ == '__main__':
    main()