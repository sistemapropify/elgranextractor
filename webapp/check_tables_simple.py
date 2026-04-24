#!/usr/bin/env python
"""
Script simple para verificar tablas en la base de datos propifai.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

from django.db import connections

def check_tables_simple():
    """Verifica las tablas en la base de datos propifai de forma simple."""
    print("=== Verificando tablas en base de datos propifai ===\n")
    
    try:
        # Verificar conexión
        conn = connections['propifai']
        cursor = conn.cursor()
        
        # Verificar si la conexión funciona
        cursor.execute('SELECT 1')
        result = cursor.fetchone()
        print(f"OK: Conexion exitosa a 'propifai': {result}")
        
        # Listar todas las tablas
        cursor.execute("""
            SELECT 
                TABLE_SCHEMA,
                TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """)
        
        tables = cursor.fetchall()
        print(f"\nTotal de tablas encontradas: {len(tables)}\n")
        
        # Mostrar primeras 20 tablas
        print("Primeras 20 tablas:")
        for i, (schema, table) in enumerate(tables[:20], 1):
            print(f"{i:3}. {schema}.{table}")
        
        if len(tables) > 20:
            print(f"... y {len(tables) - 20} mas")
        
        # Buscar tablas relacionadas con propiedades
        print("\n=== Buscando tablas relacionadas con propiedades ===\n")
        property_tables = []
        for schema, table in tables:
            table_lower = table.lower()
            if any(keyword in table_lower for keyword in ['prop', 'inmueble', 'casa', 'departamento', 'terreno', 'property']):
                property_tables.append((schema, table))
        
        if property_tables:
            print(f"Encontradas {len(property_tables)} tablas relacionadas con propiedades:\n")
            for schema, table in property_tables:
                print(f"  - {schema}.{table}")
        else:
            print("No se encontraron tablas relacionadas con propiedades.")
        
        # Verificar si existe la tabla 'properties'
        print("\n=== Verificando tabla 'properties' especificamente ===\n")
        found = False
        for schema, table in tables:
            if table.lower() == 'properties':
                found = True
                print(f"OK: Tabla 'properties' encontrada en esquema '{schema}'")
                break
        
        if not found:
            print("ERROR: Tabla 'properties' NO encontrada.")
            print("\nTablas disponibles similares:")
            for schema, table in tables:
                if 'prop' in table.lower():
                    print(f"  - {schema}.{table}")
        
        cursor.close()
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_tables_simple()