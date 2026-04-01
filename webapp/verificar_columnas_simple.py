#!/usr/bin/env python
"""
Script simple para verificar si las columnas 'condicion' y 'propiedad_verificada' existen en la tabla.
"""

import os
import sys
import django
from django.db import connection

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

def main():
    print("=== VERIFICACIÓN SIMPLE DE COLUMNAS ===\n")
    
    # Buscar tabla propiedadraw
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME LIKE '%propiedadraw%'
        """)
        tablas = cursor.fetchall()
        
        if not tablas:
            print("ERROR: No se encontró ninguna tabla 'propiedadraw'.")
            return
        
        for schema, tabla in tablas:
            print(f"Tabla: {schema}.{tabla}")
            
            # Verificar columnas específicas
            for col in ['condicion', 'propiedad_verificada']:
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? AND COLUMN_NAME = ?
                """, [schema, tabla, col])
                existe = cursor.fetchone()[0] > 0
                
                if existe:
                    print(f"  ✓ Columna '{col}' EXISTE")
                else:
                    print(f"  ✗ Columna '{col}' NO EXISTE")
            
            # Mostrar todas las columnas para referencia
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
            """, [schema, tabla])
            columnas = cursor.fetchall()
            
            print(f"\nTodas las columnas en '{tabla}':")
            for i, (col_name, data_type) in enumerate(columnas):
                print(f"  {i+1:2d}. {col_name} ({data_type})")
    
    print("\n=== INSTRUCCIONES ===")
    print("Si las columnas NO existen, necesitas agregarlas manualmente:")
    print("1. Ejecutar SQL: ALTER TABLE [schema].[tabla] ADD condicion NVARCHAR(20) NULL")
    print("2. Ejecutar SQL: ALTER TABLE [schema].[tabla] ADD propiedad_verificada BIT NULL")
    print("\nO ejecutar el script 'estado_actual.py' que intentará agregarlas automáticamente.")

if __name__ == '__main__':
    main()