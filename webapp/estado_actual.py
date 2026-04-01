#!/usr/bin/env python
"""
Script para mostrar el estado actual de la base de datos y agregar columnas si faltan.
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
    print("=== ESTADO ACTUAL DE LA BASE DE DATOS ===\n")
    
    # 1. Verificar tabla
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
            print(f"Tabla encontrada: {schema}.{tabla}")
            
            # 2. Verificar columnas
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
            """, [schema, tabla])
            columnas = cursor.fetchall()
            
            print(f"\nColumnas de la tabla '{tabla}':")
            for col_name, data_type, nullable in columnas:
                print(f"  - {col_name} ({data_type}, nullable: {nullable})")
            
            # 3. Verificar columnas específicas
            columnas_set = {col[0].lower() for col in columnas}
            print("\nVerificación de columnas requeridas:")
            for col in ['condicion', 'propiedad_verificada']:
                if col in columnas_set:
                    print(f"  ✓ '{col}' EXISTE")
                else:
                    print(f"  ✗ '{col}' NO EXISTE")
                    
                    # 4. Intentar agregar columna faltante
                    print(f"    Intentando agregar '{col}'...")
                    try:
                        if col == 'condicion':
                            cursor.execute(f"ALTER TABLE {schema}.{tabla} ADD condicion NVARCHAR(20) NULL")
                        elif col == 'propiedad_verificada':
                            cursor.execute(f"ALTER TABLE {schema}.{tabla} ADD propiedad_verificada BIT NULL")
                        print(f"    ✓ Columna '{col}' agregada.")
                    except Exception as e:
                        print(f"    ✗ Error al agregar '{col}': {e}")
            
            # 5. Contar registros
            cursor.execute(f"SELECT COUNT(*) FROM {schema}.{tabla}")
            count = cursor.fetchone()[0]
            print(f"\nTotal de registros en la tabla: {count}")
            
            # 6. Mostrar algunos registros
            if count > 0:
                cursor.execute(f"SELECT TOP 3 id, condicion, propiedad_verificada FROM {schema}.{tabla}")
                registros = cursor.fetchall()
                print("\nPrimeros 3 registros (id, condicion, propiedad_verificada):")
                for reg in registros:
                    print(f"  {reg}")
    
    print("\n=== RECOMENDACIONES ===")
    print("1. Si las columnas se agregaron, reinicia el servidor Django.")
    print("2. Si las columnas no se pudieron agregar, verifica los permisos de la base de datos.")
    print("3. Si el error persiste, puede ser necesario recrear la tabla completa.")
    print("\nPara recrear la tabla, puedes ejecutar:")
    print("   python manage.py migrate ingestas zero")
    print("   python manage.py migrate ingestas")

if __name__ == '__main__':
    main()