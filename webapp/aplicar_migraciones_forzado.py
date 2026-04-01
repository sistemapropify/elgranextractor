#!/usr/bin/env python
"""
Script para aplicar migraciones pendientes de manera forzada.
"""

import os
import sys
import django
from django.core.management import execute_from_command_line

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')
django.setup()

def main():
    print("=== Aplicando migraciones pendientes ===")
    
    # Primero, mostrar estado
    print("\n1. Mostrando estado de migraciones:")
    try:
        execute_from_command_line(['manage.py', 'showmigrations', 'ingestas'])
    except Exception as e:
        print(f"Error: {e}")
    
    # Aplicar migraciones
    print("\n2. Aplicando migraciones...")
    try:
        execute_from_command_line(['manage.py', 'migrate', 'ingestas'])
    except Exception as e:
        print(f"Error al aplicar migraciones: {e}")
        sys.exit(1)
    
    # Aplicar migraciones de todo el proyecto por si acaso
    print("\n3. Aplicando migraciones de todo el proyecto...")
    try:
        execute_from_command_line(['manage.py', 'migrate'])
    except Exception as e:
        print(f"Error al aplicar migraciones globales: {e}")
    
    # Verificar estado final
    print("\n4. Estado final de migraciones:")
    try:
        execute_from_command_line(['manage.py', 'showmigrations', 'ingestas'])
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n¡Proceso completado!")

if __name__ == '__main__':
    main()