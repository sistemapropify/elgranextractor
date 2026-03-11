#!/usr/bin/env python
"""
Script para verificar las columnas de imágenes en la tabla properties de la base de datos Propifai.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.db import connections

def check_propifai_table():
    """Verifica las columnas de la tabla properties en la base de datos propifai."""
    try:
        with connections['propifai'].cursor() as cursor:
            # Obtener columnas de la tabla properties
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'properties'
                ORDER BY ORDINAL_POSITION
            """)
            columns = cursor.fetchall()
            
            print("Columnas de la tabla 'properties' en base de datos Propifai:")
            print("-" * 80)
            for col_name, data_type, is_nullable in columns:
                print(f"{col_name:30} {data_type:20} {'NULL' if is_nullable == 'YES' else 'NOT NULL'}")
            
            # Buscar columnas relacionadas con imágenes
            print("\nColumnas que podrían contener URLs de imágenes:")
            print("-" * 80)
            image_columns = []
            for col_name, data_type, is_nullable in columns:
                if any(img_keyword in col_name.lower() for img_keyword in ['image', 'img', 'photo', 'picture', 'url', 'thumbnail', 'media']):
                    image_columns.append((col_name, data_type))
                    print(f"{col_name:30} {data_type:20}")
            
            if not image_columns:
                print("No se encontraron columnas obvias para imágenes.")
                
            # Ver algunos registros de ejemplo para ver los datos
            print("\nEjemplo de registros (primeros 5):")
            print("-" * 80)
            cursor.execute("SELECT TOP 5 * FROM properties")
            rows = cursor.fetchall()
            if rows:
                # Obtener nombres de columnas
                cursor.execute("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'properties'
                    ORDER BY ORDINAL_POSITION
                """)
                col_names = [row[0] for row in cursor.fetchall()]
                
                for i, row in enumerate(rows):
                    print(f"\nRegistro {i+1}:")
                    for j, value in enumerate(row):
                        if col_names[j].lower() in ['image', 'img', 'photo', 'picture', 'url', 'thumbnail']:
                            print(f"  {col_names[j]}: {value}")
            
    except Exception as e:
        print(f"Error al consultar la base de datos: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_propifai_table()