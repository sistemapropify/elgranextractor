#!/usr/bin/env python
"""
Script para explorar la estructura de la tabla 'properties' en propifai.
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

def explore_properties_table():
    """Explora la estructura de la tabla properties."""
    try:
        connection = connections['propifai']
        with connection.cursor() as cursor:
            # Obtener columnas de la tabla properties
            cursor.execute("""
                SELECT 
                    COLUMN_NAME, 
                    DATA_TYPE, 
                    IS_NULLABLE,
                    CHARACTER_MAXIMUM_LENGTH,
                    COLUMN_DEFAULT,
                    ORDINAL_POSITION
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'properties'
                ORDER BY ORDINAL_POSITION
            """)
            columns = cursor.fetchall()
            
            print("Estructura de la tabla dbo.properties:")
            print("-" * 80)
            print(f"Total de columnas: {len(columns)}")
            print("-" * 80)
            
            for col_name, data_type, is_nullable, char_max_len, col_default, ordinal in columns:
                type_info = data_type
                if char_max_len:
                    type_info += f"({char_max_len})"
                default_info = f", default: {col_default}" if col_default else ""
                print(f"{ordinal:2}. {col_name:30} {type_info:20} nullable: {is_nullable}{default_info}")
            
            # Obtener algunas filas de ejemplo
            print("\n" + "-" * 80)
            print("Primeras 3 filas de ejemplo:")
            print("-" * 80)
            
            cursor.execute("SELECT TOP 3 * FROM dbo.properties")
            rows = cursor.fetchall()
            
            # Obtener nombres de columnas
            col_names = [col[0] for col in columns]
            
            for i, row in enumerate(rows):
                print(f"\nFila {i+1}:")
                for j, value in enumerate(row):
                    col_name = col_names[j]
                    print(f"  {col_name}: {value}")
            
            # Buscar columnas de ubicación (latitud, longitud, dirección)
            location_cols = []
            for col_name, data_type, is_nullable, char_max_len, col_default, ordinal in columns:
                col_lower = col_name.lower()
                if any(keyword in col_lower for keyword in ['lat', 'lng', 'lon', 'latitude', 'longitude', 'address', 'direccion', 'ubicacion']):
                    location_cols.append((col_name, data_type))
            
            if location_cols:
                print("\n" + "-" * 80)
                print("Columnas de ubicación encontradas:")
                for col_name, data_type in location_cols:
                    print(f"  - {col_name} ({data_type})")
            
            return columns
            
    except Exception as e:
        print(f"[ERROR] Error explorando tabla: {e}")
        return []

if __name__ == "__main__":
    print("Explorando estructura de tabla 'properties' en base de datos 'propifai'...")
    columns = explore_properties_table()
    print(f"\nTotal de columnas analizadas: {len(columns)}")