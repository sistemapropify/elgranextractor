#!/usr/bin/env python
"""
Script para examinar la tabla property_images en la base de datos Propifai.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.db import connections

def check_property_images_table():
    """Examina la tabla property_images."""
    try:
        with connections['propifai'].cursor() as cursor:
            # Verificar si la tabla existe
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'property_images'
            """)
            table_exists = cursor.fetchone()
            
            if not table_exists:
                print("La tabla 'property_images' no existe en la base de datos Propifai.")
                # Buscar tablas similares
                cursor.execute("""
                    SELECT TABLE_NAME 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_NAME LIKE '%image%' OR TABLE_NAME LIKE '%photo%'
                """)
                similar_tables = cursor.fetchall()
                if similar_tables:
                    print("Tablas similares encontradas:")
                    for table in similar_tables:
                        print(f"  - {table[0]}")
                return
            
            print("Tabla 'property_images' encontrada.")
            
            # Obtener columnas
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'property_images'
                ORDER BY ORDINAL_POSITION
            """)
            columns = cursor.fetchall()
            
            print("\nColumnas de la tabla 'property_images':")
            print("-" * 80)
            for col_name, data_type, is_nullable, char_max_len in columns:
                type_info = data_type
                if char_max_len:
                    type_info += f"({char_max_len})"
                print(f"{col_name:30} {type_info:20} {'NULL' if is_nullable == 'YES' else 'NOT NULL'}")
            
            # Ver algunos registros de ejemplo
            print("\nRegistros de ejemplo (primeros 5):")
            print("-" * 80)
            cursor.execute("SELECT TOP 5 * FROM property_images")
            rows = cursor.fetchall()
            
            if rows:
                # Obtener nombres de columnas
                col_names = [desc[0] for desc in cursor.description]
                
                for i, row in enumerate(rows):
                    print(f"\nRegistro {i+1}:")
                    for j, value in enumerate(row):
                        col_name = col_names[j]
                        # Mostrar solo columnas relevantes para imágenes
                        if any(img_keyword in col_name.lower() for img_keyword in ['url', 'path', 'image', 'file', 'name']):
                            print(f"  {col_name}: {value}")
                        elif j < 5:  # Mostrar primeras 5 columnas siempre
                            print(f"  {col_name}: {value}")
            
            # Verificar relación con properties
            print("\nRelación con tabla properties:")
            print("-" * 80)
            # Buscar columnas que puedan referenciar property_id
            foreign_keys = []
            for col_name, data_type, is_nullable, char_max_len in columns:
                if 'property' in col_name.lower() or col_name.lower() in ['property_id', 'prop_id', 'propertyid']:
                    foreign_keys.append(col_name)
            
            if foreign_keys:
                print(f"Posibles claves foráneas: {', '.join(foreign_keys)}")
                # Verificar algunos registros para ver la relación
                for fk in foreign_keys[:1]:  # Solo la primera
                    cursor.execute(f"SELECT TOP 3 {fk}, COUNT(*) as count FROM property_images GROUP BY {fk} ORDER BY count DESC")
                    fk_values = cursor.fetchall()
                    if fk_values:
                        print(f"\nValores de {fk} (top 3):")
                        for fk_value, count in fk_values:
                            print(f"  {fk_value}: {count} imágenes")
            else:
                print("No se encontraron columnas obvias para relación con properties.")
                
    except Exception as e:
        print(f"Error al consultar la base de datos: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_property_images_table()