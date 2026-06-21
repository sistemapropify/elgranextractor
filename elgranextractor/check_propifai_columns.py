#!/usr/bin/env python
"""
Verificar columnas de la tabla properties en base de datos propifai
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.db import connections

def check_propifai_columns():
    """Verificar columnas de la tabla properties"""
    
    print("Verificando columnas de la tabla properties en base de datos propifai")
    
    try:
        conn = connections['propifai']
        with conn.cursor() as cursor:
            # Obtener columnas de la tabla properties
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'properties'
                ORDER BY ORDINAL_POSITION
            """)
            
            columns = cursor.fetchall()
            print(f"\nColumnas encontradas ({len(columns)}):")
            for col in columns:
                print(f"  {col[0]}: {col[1]} (nullable: {col[2]}, max_len: {col[3]})")
            
            # Verificar también la tabla propifai_propiedad por si acaso
            print("\n\nVerificando tabla propifai_propiedad...")
            try:
                cursor.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'propifai_propiedad'
                    ORDER BY ORDINAL_POSITION
                """)
                columns2 = cursor.fetchall()
                print(f"Columnas en propifai_propiedad ({len(columns2)}):")
                for col in columns2:
                    print(f"  {col[0]}: {col[1]} (nullable: {col[2]}, max_len: {col[3]})")
            except:
                print("  Tabla propifai_propiedad no existe")
                
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    check_propifai_columns()