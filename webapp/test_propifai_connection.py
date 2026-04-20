#!/usr/bin/env python
"""
Script para probar la conexión a la base de datos 'propifai' (dbpropify)
y listar sus tablas.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.db import connections

def test_propifai_connection():
    """Prueba la conexión a la base de datos 'propifai'."""
    print("=== Probando conexión a base de datos 'propifai' ===")
    
    try:
        # Verificar si la conexión existe
        if 'propifai' not in connections:
            print("ERROR: La conexión 'propifai' no está definida en settings.DATABASES")
            return False
        
        conn = connections['propifai']
        print(f"Conexión obtenida: {conn}")
        
        # Probar la conexión
        with conn.cursor() as cursor:
            cursor.execute("SELECT DB_NAME()")
            db_name = cursor.fetchone()[0]
            print(f"Conectado a base de datos: {db_name}")
            
            # Listar tablas
            cursor.execute("""
                SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = 'dbo'
                ORDER BY TABLE_NAME
            """)
            tables = cursor.fetchall()
            
            print(f"\n=== Tablas en {db_name} (esquema dbo) ===")
            for schema, name, table_type in tables:
                if table_type == 'BASE TABLE':
                    print(f"  - {name} (tabla)")
                else:
                    print(f"  - {name} ({table_type})")
            
            print(f"\nTotal de tablas encontradas: {len(tables)}")
            return True
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_default_connection():
    """Prueba la conexión a la base de datos 'default' para comparar."""
    print("\n=== Probando conexión a base de datos 'default' ===")
    
    try:
        conn = connections['default']
        print(f"Conexión obtenida: {conn}")
        
        with conn.cursor() as cursor:
            cursor.execute("SELECT DB_NAME()")
            db_name = cursor.fetchone()[0]
            print(f"Conectado a base de datos: {db_name}")
            
            cursor.execute("""
                SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = 'dbo'
                ORDER BY TABLE_NAME
            """)
            tables = cursor.fetchall()
            
            print(f"Total de tablas en 'default': {len(tables)}")
            return True
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == '__main__':
    print("Iniciando prueba de conexión a bases de datos...")
    
    # Probar ambas conexiones
    success1 = test_default_connection()
    success2 = test_propifai_connection()
    
    if success1 and success2:
        print("\n✓ Ambas conexiones funcionan correctamente")
    else:
        print("\n✗ Hubo problemas con alguna conexión")
        sys.exit(1)