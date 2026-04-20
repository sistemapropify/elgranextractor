#!/usr/bin/env python
"""
Script para verificar la base de datos 'propifai'.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.db import connections

def main():
    print("=== Verificando conexión a base de datos 'propifai' ===")
    
    # Verificar si existe la conexión
    if 'propifai' not in connections:
        print("ERROR: No hay conexión 'propifai' en connections")
        return
    
    conn = connections['propifai']
    
    try:
        # Intentar conectar
        conn.ensure_connection()
        print("✅ Conexión 'propifai' establecida")
        print(f"   Base de datos: {conn.settings_dict.get('NAME')}")
        print(f"   Host: {conn.settings_dict.get('HOST')}")
        
        # Listar tablas
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT TABLE_SCHEMA, TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """)
            tables = cursor.fetchall()
            
            print(f"\nTotal de tablas en base de datos 'propifai': {len(tables)}")
            print("\nTablas relacionadas con 'propiedad' o 'property':")
            for schema, table in tables:
                table_lower = table.lower()
                if 'propiedad' in table_lower or 'property' in table_lower:
                    print(f"  - {schema}.{table}")
            
            # Buscar tabla 'properties'
            print("\n=== Buscando tabla 'properties' ===")
            cursor.execute("""
                SELECT TABLE_SCHEMA, TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'properties'
            """)
            result = cursor.fetchone()
            if result:
                print(f"Tabla 'properties' encontrada: {result[0]}.{result[1]}")
                
                # Contar registros
                cursor.execute(f"SELECT COUNT(*) FROM {result[0]}.{result[1]}")
                count = cursor.fetchone()[0]
                print(f"Registros en tabla: {count}")
            else:
                print("Tabla 'properties' NO encontrada")
                
                # Listar todas las tablas para referencia
                print("\nTodas las tablas (primeras 15):")
                for i, (schema, table) in enumerate(tables[:15]):
                    print(f"  {i+1:2d}. {schema}.{table}")
                    
    except Exception as e:
        print(f"❌ Error al conectar a base de datos 'propifai': {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()