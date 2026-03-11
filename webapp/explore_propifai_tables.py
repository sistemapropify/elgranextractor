#!/usr/bin/env python
"""
Script para explorar las tablas en la base de datos Propifai.
"""
import os
import sys
import django
from django.db import connections

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

def explorar_tablas():
    print("EXPLORANDO TABLAS EN LA BASE DE DATOS PROPIFAI")
    print("=" * 60)
    
    # Conectar a la base de datos propifai
    connection = connections['propifai']
    
    try:
        with connection.cursor() as cursor:
            # Obtener todas las tablas
            cursor.execute("""
                SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_SCHEMA, TABLE_NAME
            """)
            
            tablas = cursor.fetchall()
            
            print(f"\nTotal de tablas: {len(tablas)}")
            print("\nLista de tablas:")
            print("-" * 80)
            for schema, table_name, table_type in tablas:
                print(f"{schema}.{table_name}")
            
            # Buscar tablas relacionadas con ubicaciones
            print("\n\nBUSCANDO TABLAS DE UBICACIÓN:")
            print("-" * 80)
            
            tablas_ubicacion = []
            for schema, table_name, table_type in tablas:
                if any(keyword in table_name.lower() for keyword in 
                      ['departamento', 'provincia', 'distrito', 'region', 'city', 'state', 'location', 'ubigeo']):
                    tablas_ubicacion.append((schema, table_name))
            
            if tablas_ubicacion:
                print("Tablas de ubicación encontradas:")
                for schema, table_name in tablas_ubicacion:
                    print(f"  - {schema}.{table_name}")
                    
                    # Mostrar columnas de estas tablas
                    cursor.execute(f"""
                        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                        ORDER BY ORDINAL_POSITION
                    """, [schema, table_name])
                    
                    columnas = cursor.fetchall()
                    print(f"    Columnas ({len(columnas)}):")
                    for col_name, data_type, nullable in columnas:
                        print(f"      {col_name} ({data_type}) {'NULL' if nullable == 'YES' else 'NOT NULL'}")
                    
                    # Mostrar algunas filas de ejemplo
                    cursor.execute(f"SELECT TOP 5 * FROM [{schema}].[{table_name}]")
                    filas = cursor.fetchall()
                    if filas:
                        print(f"    Primeras 5 filas:")
                        for fila in filas:
                            # Truncar valores largos
                            fila_str = ', '.join([str(val)[:50] + '...' if val and len(str(val)) > 50 else str(val) for val in fila])
                            print(f"      {fila_str}")
                    print()
            else:
                print("No se encontraron tablas de ubicación con nombres obvios.")
            
            # También buscar en la tabla de propiedades para ver campos de ubicación
            print("\n\nEXPLORANDO TABLA DE PROPIEDADES (properties):")
            print("-" * 80)
            
            # Buscar tabla de propiedades (puede llamarse 'properties', 'property', 'propiedades', etc.)
            tablas_propiedades = []
            for schema, table_name, table_type in tablas:
                if any(keyword in table_name.lower() for keyword in 
                      ['property', 'propiedad', 'listing', 'inmueble']):
                    tablas_propiedades.append((schema, table_name))
            
            if tablas_propiedades:
                for schema, table_name in tablas_propiedades:
                    print(f"\nTabla de propiedades: {schema}.{table_name}")
                    
                    # Mostrar columnas relacionadas con ubicación
                    cursor.execute(f"""
                        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                        AND COLUMN_NAME LIKE '%departamento%' 
                           OR COLUMN_NAME LIKE '%provincia%'
                           OR COLUMN_NAME LIKE '%distrito%'
                           OR COLUMN_NAME LIKE '%city%'
                           OR COLUMN_NAME LIKE '%state%'
                           OR COLUMN_NAME LIKE '%region%'
                           OR COLUMN_NAME LIKE '%location%'
                        ORDER BY ORDINAL_POSITION
                    """, [schema, table_name])
                    
                    columnas_ubic = cursor.fetchall()
                    if columnas_ubic:
                        print(f"  Columnas de ubicación encontradas:")
                        for col_name, data_type, nullable in columnas_ubic:
                            print(f"    {col_name} ({data_type})")
                    else:
                        print(f"  No se encontraron columnas de ubicación con nombres obvios.")
                    
                    # Mostrar todas las columnas (solo nombres)
                    cursor.execute(f"""
                        SELECT COLUMN_NAME, DATA_TYPE
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                        ORDER BY ORDINAL_POSITION
                    """, [schema, table_name])
                    
                    todas_columnas = cursor.fetchall()
                    print(f"  Total de columnas: {len(todas_columnas)}")
                    print(f"  Primeras 10 columnas: {[col[0] for col in todas_columnas[:10]]}")
                    
    except Exception as e:
        print(f"Error al explorar tablas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    explorar_tablas()