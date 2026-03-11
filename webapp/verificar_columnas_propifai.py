#!/usr/bin/env python
"""
Script para verificar las columnas de ubicación en la tabla properties de Propifai.
"""
import os
import sys
import django
from django.db import connections

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

def verificar_columnas():
    print("VERIFICANDO COLUMNAS DE UBICACIÓN EN PROPIFAI")
    print("=" * 70)
    
    # Conectar a la base de datos propifai
    connection = connections['propifai']
    
    try:
        with connection.cursor() as cursor:
            # 1. Verificar todas las columnas de la tabla properties
            print("\n1. TODAS LAS COLUMNAS DE 'properties':")
            print("-" * 50)
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'properties' 
                AND TABLE_SCHEMA = 'dbo'
                ORDER BY ORDINAL_POSITION
            """)
            todas_columnas = cursor.fetchall()
            print(f"Total de columnas: {len(todas_columnas)}")
            
            # Mostrar solo las primeras 20 columnas para no saturar
            for i, (col_name, data_type, is_nullable) in enumerate(todas_columnas[:20]):
                print(f"  {i+1:2d}. {col_name:30s} ({data_type:15s}) NULLABLE: {is_nullable}")
            
            if len(todas_columnas) > 20:
                print(f"  ... y {len(todas_columnas) - 20} columnas más")
            
            # 2. Buscar específicamente columnas de ubicación
            print("\n2. COLUMNAS DE UBICACIÓN ESPECÍFICAS:")
            print("-" * 50)
            
            # Buscar por patrones comunes
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'properties' 
                AND TABLE_SCHEMA = 'dbo'
                AND (
                    COLUMN_NAME LIKE '%department%' 
                    OR COLUMN_NAME LIKE '%province%' 
                    OR COLUMN_NAME LIKE '%district%'
                    OR COLUMN_NAME LIKE '%location%'
                    OR COLUMN_NAME LIKE '%city%'
                    OR COLUMN_NAME LIKE '%region%'
                    OR COLUMN_NAME LIKE '%country%'
                    OR COLUMN_NAME LIKE '%address%'
                )
                ORDER BY COLUMN_NAME
            """)
            columnas_ubic = cursor.fetchall()
            
            if columnas_ubic:
                print(f"Encontradas {len(columnas_ubic)} columnas de ubicación:")
                for col_name, data_type in columnas_ubic:
                    print(f"  - {col_name} ({data_type})")
            else:
                print("No se encontraron columnas de ubicación con esos nombres.")
            
            # 3. Verificar algunos registros para ver los valores reales
            print("\n3. VALORES DE EJEMPLO EN PROPIEDADES:")
            print("-" * 50)
            
            # Primero obtener los nombres de columnas que parecen ser de ubicación
            columnas_interes = []
            for col_name, data_type in columnas_ubic:
                columnas_interes.append(col_name)
            
            if columnas_interes:
                # Construir consulta dinámica
                columnas_str = ", ".join(columnas_interes[:5])  # Limitar a 5 columnas
                cursor.execute(f"""
                    SELECT TOP 5 id, {columnas_str}
                    FROM properties 
                    WHERE {' OR '.join([f'{col} IS NOT NULL' for col in columnas_interes[:5]])}
                    ORDER BY id
                """)
                propiedades = cursor.fetchall()
                
                if propiedades:
                    print(f"Ejemplos de propiedades con valores de ubicación:")
                    for prop in propiedades:
                        prop_id = prop[0]
                        valores = prop[1:]
                        print(f"\n  Propiedad ID: {prop_id}")
                        for i, valor in enumerate(valores):
                            col_name = columnas_interes[i]
                            print(f"    {col_name}: {valor}")
                else:
                    print("No se encontraron propiedades con valores en esas columnas.")
            
            # 4. Verificar tablas de mapeo
            print("\n4. TABLAS DE MAPEO DISPONIBLES:")
            print("-" * 50)
            
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = 'dbo'
                AND (
                    TABLE_NAME LIKE '%department%' 
                    OR TABLE_NAME LIKE '%province%' 
                    OR TABLE_NAME LIKE '%district%'
                    OR TABLE_NAME LIKE '%location%'
                    OR TABLE_NAME LIKE '%city%'
                )
                ORDER BY TABLE_NAME
            """)
            tablas_mapeo = cursor.fetchall()
            
            if tablas_mapeo:
                print(f"Tablas de mapeo encontradas:")
                for tabla in tablas_mapeo:
                    tabla_nombre = tabla[0]
                    print(f"  - {tabla_nombre}")
                    
                    # Verificar estructura de cada tabla
                    cursor.execute(f"""
                        SELECT COLUMN_NAME, DATA_TYPE
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_NAME = '{tabla_nombre}' 
                        AND TABLE_SCHEMA = 'dbo'
                        ORDER BY ORDINAL_POSITION
                    """)
                    columnas_tabla = cursor.fetchall()
                    print(f"    Columnas: {', '.join([f'{c[0]} ({c[1]})' for c in columnas_tabla[:3]])}")
                    if len(columnas_tabla) > 3:
                        print(f"    ... y {len(columnas_tabla) - 3} más")
            else:
                print("No se encontraron tablas de mapeo.")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    verificar_columnas()