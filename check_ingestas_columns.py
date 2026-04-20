#!/usr/bin/env python
"""
Verificar columnas de la tabla ingestas_propiedadraw
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.db import connections

def check_ingestas_columns():
    """Verificar columnas de la tabla ingestas_propiedadraw"""
    
    print("Verificando columnas de la tabla ingestas_propiedadraw")
    
    try:
        conn = connections['default']
        with conn.cursor() as cursor:
            # Obtener columnas de la tabla ingestas_propiedadraw
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'ingestas_propiedadraw'
                ORDER BY ORDINAL_POSITION
            """)
            
            columns = cursor.fetchall()
            print(f"\nColumnas encontradas ({len(columns)}):")
            for col in columns:
                print(f"  {col[0]}: {col[1]} (nullable: {col[2]}, max_len: {col[3]})")
            
            # Verificar si existe la columna 'activo'
            active_columns = [col[0] for col in columns if 'activo' in col[0].lower()]
            print(f"\nColumnas con 'activo': {active_columns}")
            
            # Verificar algunas columnas específicas mencionadas en el error
            target_columns = ['titulo', 'descripcion', 'direccion', 'precio', 'moneda', 
                            'area_construida', 'area_total', 'habitaciones', 'banos',
                            'estacionamientos', 'fecha_scraping', 'fuente', 'condicion',
                            'tipo_propiedad', 'distrito']
            
            print("\nVerificando columnas específicas:")
            for target in target_columns:
                found = any(target in col[0].lower() for col in columns)
                print(f"  {target}: {'ENCONTRADA' if found else 'NO ENCONTRADA'}")
                
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    check_ingestas_columns()