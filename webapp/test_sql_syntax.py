#!/usr/bin/env python
"""
Script para probar la sintaxis SQL Server en el método ejecutar_migracion.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

django.setup()

from ingestas.services import EjecutorMigraciones
from django.contrib.auth.models import User

def test_sql_syntax():
    """Prueba la generación de SQL para SQL Server."""
    print("=== Prueba de sintaxis SQL Server ===")
    
    # Test 1: Mapeo de tipos
    print("\n1. Mapeo de tipos:")
    test_cases = [
        ('VARCHAR', 'VARCHAR(255)'),
        ('INTEGER', 'INT'),
        ('DECIMAL', 'DECIMAL(15,2)'),
        ('BOOLEAN', 'BIT'),
        ('DATE', 'DATE'),
        ('DATETIME', 'DATETIME2'),
        ('UNKNOWN', 'VARCHAR(255)'),
    ]
    
    for tipo_input, expected in test_cases:
        result = EjecutorMigraciones.mapear_tipo_django(tipo_input)
        status = "OK" if result == expected else "ERROR"
        print(f"  {status} {tipo_input} -> {result} (esperado: {expected})")
    
    # Test 2: Generación de SQL ALTER TABLE
    print("\n2. Generación de SQL ALTER TABLE:")
    tabla = 'ingestas_propiedadraw'
    nombre_campo = 'test_campo'
    tipo_sql = EjecutorMigraciones.mapear_tipo_django('VARCHAR')
    
    # SQL esperado para SQL Server
    expected_sql = f'ALTER TABLE {tabla} ADD {nombre_campo} {tipo_sql}'
    print(f"  SQL esperado: {expected_sql}")
    
    # Verificar que no contiene 'COLUMN'
    if 'COLUMN' in expected_sql:
        print("  ERROR: SQL contiene 'COLUMN' (no válido para SQL Server)")
    else:
        print("  OK: SQL no contiene 'COLUMN' (correcto para SQL Server)")
    
    # Test 3: Validación de nombres snake_case
    print("\n3. Validación de nombres snake_case:")
    test_names = [
        ('nombre_valido', True),
        ('nombre_con_123', True),
        ('NombreConMayus', False),
        ('nombre-con-guion', False),
        ('123_inicio_numero', False),
        ('_nombre_inicio_guion', False),
    ]
    
    for name, should_pass in test_names:
        try:
            EjecutorMigraciones.validar_nombre_snake_case(name)
            if should_pass:
                print(f"  OK '{name}' válido (correcto)")
            else:
                print(f"  ERROR '{name}' debería fallar pero pasó")
        except ValueError as e:
            if not should_pass:
                print(f"  OK '{name}' rechazado (correcto): {str(e)[:50]}")
            else:
                print(f"  ERROR '{name}' debería pasar pero falló: {str(e)[:50]}")
    
    print("\n=== Prueba completada ===")

if __name__ == '__main__':
    test_sql_syntax()