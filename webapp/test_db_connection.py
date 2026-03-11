#!/usr/bin/env python
"""
Script para probar la conexión a ambas bases de datos.
"""
import os
import sys
import django

# Configurar Django - ajustar para ejecutar desde el directorio webapp
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

django.setup()

from django.db import connections

def test_database_connection(db_alias):
    """Prueba la conexión a una base de datos específica."""
    try:
        connection = connections[db_alias]
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            print(f"[OK] Conexión exitosa a la base de datos '{db_alias}': {result}")
            return True
    except Exception as e:
        print(f"[ERROR] Error conectando a la base de datos '{db_alias}': {e}")
        return False

if __name__ == "__main__":
    print("Probando conexiones a bases de datos...")
    print("-" * 50)
    
    # Probar conexión a base de datos default
    default_ok = test_database_connection('default')
    
    # Probar conexión a base de datos propifai
    propifai_ok = test_database_connection('propifai')
    
    print("-" * 50)
    
    if default_ok and propifai_ok:
        print("[SUCCESS] Ambas conexiones a bases de datos funcionan correctamente.")
    elif default_ok:
        print("[WARNING] Solo la conexión a 'default' funciona. La conexión a 'propifai' falló.")
    elif propifai_ok:
        print("[WARNING] Solo la conexión a 'propifai' funciona. La conexión a 'default' falló.")
    else:
        print("[FAILURE] Ambas conexiones a bases de datos fallaron.")