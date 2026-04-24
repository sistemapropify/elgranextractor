#!/usr/bin/env python
"""
Script para probar la validación de la tabla 'properties'.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

from intelligence.services.schema_discovery import SchemaDiscoveryService

def test_table_validation():
    """Prueba la validación de la tabla 'properties'."""
    print("=== Probando validación de tabla 'properties' ===\n")
    
    try:
        # Probar con base de datos 'propifai'
        print("1. Probando con database_alias='propifai':")
        exists = SchemaDiscoveryService.validate_table(
            table_name='properties',
            schema='dbo',
            database_alias='propifai'
        )
        print(f"   Resultado: {exists}")
        
        if exists:
            print("   OK: La tabla existe en 'propifai'")
        else:
            print("   ERROR: La tabla NO existe en 'propifai'")
        
        # Probar con base de datos 'default' para comparar
        print("\n2. Probando con database_alias='default':")
        exists_default = SchemaDiscoveryService.validate_table(
            table_name='properties',
            schema='dbo',
            database_alias='default'
        )
        print(f"   Resultado: {exists_default}")
        
        # Probar análisis de esquema
        print("\n3. Probando análisis de esquema en 'propifai':")
        schema_analysis = SchemaDiscoveryService.analyze_table_schema(
            table_name='properties',
            schema='dbo',
            database_alias='propifai'
        )
        
        if schema_analysis.get('exists', False):
            print(f"   OK: Esquema analizado exitosamente")
            print(f"   Columnas encontradas: {len(schema_analysis.get('columns', []))}")
            print(f"   Primary key: {schema_analysis.get('primary_key', 'N/A')}")
            
            # Mostrar primeras 5 columnas
            columns = schema_analysis.get('columns', [])
            print(f"   Primeras 5 columnas:")
            for i, col in enumerate(columns[:5], 1):
                print(f"     {i}. {col.get('name', 'N/A')} ({col.get('type', 'N/A')})")
            
            if len(columns) > 5:
                print(f"   ... y {len(columns) - 5} columnas mas")
        else:
            print(f"   ERROR: {schema_analysis.get('error', 'Error desconocido')}")
        
        # Verificar conexiones de base de datos
        print("\n4. Verificando conexiones de base de datos:")
        from django.db import connections
        
        for alias in ['default', 'propifai']:
            try:
                conn = connections[alias]
                cursor = conn.cursor()
                cursor.execute('SELECT DB_NAME()')
                db_name = cursor.fetchone()[0]
                print(f"   {alias}: Conectado a '{db_name}'")
                cursor.close()
            except Exception as e:
                print(f"   {alias}: ERROR - {e}")
        
    except Exception as e:
        print(f"ERROR general: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_table_validation()