#!/usr/bin/env python
"""
Script para verificar el nombre real de la tabla de propiedades.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.db import connection

def main():
    print("=== Verificando tablas en la base de datos ===")
    
    # Listar todas las tablas
    with connection.cursor() as cursor:
        # Para SQL Server
        cursor.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        tables = cursor.fetchall()
        
        print(f"Total de tablas: {len(tables)}")
        print("\nTablas relacionadas con 'propiedad' o 'property':")
        for schema, table in tables:
            table_lower = table.lower()
            if 'propiedad' in table_lower or 'property' in table_lower or 'propifai' in table_lower:
                print(f"  - {schema}.{table}")
        
        print("\nTodas las tablas (primeras 20):")
        for i, (schema, table) in enumerate(tables[:20]):
            print(f"  {i+1:2d}. {schema}.{table}")
        
        # Verificar específicamente la tabla 'properties'
        print("\n=== Buscando tabla 'properties' ===")
        cursor.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME = 'properties'
        """)
        result = cursor.fetchone()
        if result:
            print(f"Tabla 'properties' encontrada: {result[0]}.{result[1]}")
        else:
            print("Tabla 'properties' NO encontrada")
            
        # Buscar tablas que contengan 'propifai'
        print("\n=== Buscando tablas con 'propifai' ===")
        cursor.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME LIKE '%propifai%'
        """)
        propifai_tables = cursor.fetchall()
        for schema, table in propifai_tables:
            print(f"  - {schema}.{table}")
            
        # Verificar el modelo PropifaiProperty
        from propifai.models import PropifaiProperty
        print(f"\n=== Modelo PropifaiProperty ===")
        print(f"db_table: {PropifaiProperty._meta.db_table}")
        print(f"db_table (con schema): {PropifaiProperty._meta.db_table}")
        
        # Intentar contar registros
        try:
            count = PropifaiProperty.objects.count()
            print(f"PropifaiProperty.objects.count(): {count}")
        except Exception as e:
            print(f"Error al contar: {e}")

if __name__ == '__main__':
    main()