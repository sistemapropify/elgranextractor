#!/usr/bin/env python
"""
Script para verificar tablas relacionadas con imágenes en la base de datos Propifai.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.db import connections

def check_image_tables():
    """Verifica tablas que puedan contener imágenes en la base de datos propifai."""
    try:
        with connections['propifai'].cursor() as cursor:
            # Obtener todas las tablas
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """)
            tables = cursor.fetchall()
            
            print("Tablas en la base de datos Propifai:")
            print("-" * 80)
            for table_name, in tables:
                print(f"  {table_name}")
            
            # Buscar tablas con nombres relacionados a imágenes
            print("\nTablas que podrían contener imágenes:")
            print("-" * 80)
            image_tables = []
            for table_name, in tables:
                if any(img_keyword in table_name.lower() for img_keyword in ['image', 'img', 'photo', 'picture', 'media', 'gallery', 'attachment']):
                    image_tables.append(table_name)
            
            for table_name in image_tables:
                print(f"\nTabla: {table_name}")
                # Obtener columnas de esta tabla
                cursor.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = ?
                    ORDER BY ORDINAL_POSITION
                """, [table_name])
                columns = cursor.fetchall()
                for col_name, data_type, is_nullable in columns:
                    print(f"  {col_name:30} {data_type:20} {'NULL' if is_nullable == 'YES' else 'NOT NULL'}")
            
            if not image_tables:
                print("No se encontraron tablas obvias para imágenes.")
                
            # Verificar si hay una tabla de propiedades_imagenes o similar
            print("\nBuscando tablas con relación a properties:")
            print("-" * 80)
            for table_name, in tables:
                if 'property' in table_name.lower() and 'image' in table_name.lower():
                    print(f"Tabla encontrada: {table_name}")
                    cursor.execute("SELECT TOP 3 * FROM {}".format(table_name))
                    rows = cursor.fetchall()
                    if rows:
                        print(f"  Primeros 3 registros:")
                        for row in rows:
                            print(f"    {row}")
            
            # Verificar si hay una columna de imagen en la tabla properties que no vimos antes
            print("\nRevisando columnas de properties con más detalle:")
            print("-" * 80)
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'properties'
                ORDER BY ORDINAL_POSITION
            """)
            columns = cursor.fetchall()
            for col_name, data_type, char_max_len in columns:
                if char_max_len:
                    print(f"{col_name:30} {data_type:20} (max: {char_max_len})")
                else:
                    print(f"{col_name:30} {data_type:20}")
                    
    except Exception as e:
        print(f"Error al consultar la base de datos: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_image_tables()