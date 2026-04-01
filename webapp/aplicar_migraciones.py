#!/usr/bin/env python
"""
Script para aplicar migraciones pendientes de la app ingestas.
"""

import os
import sys
import django
from django.core.management import execute_from_command_line

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')

def main():
    print("Aplicando migraciones para la app 'ingestas'...")
    
    # Ejecutar migrate
    try:
        execute_from_command_line(['manage.py', 'migrate', 'ingestas'])
        print("Migraciones aplicadas exitosamente.")
    except Exception as e:
        print(f"Error al aplicar migraciones: {e}")
        sys.exit(1)
    
    # Verificar estado
    print("\nVerificando estado de migraciones...")
    try:
        execute_from_command_line(['manage.py', 'showmigrations', 'ingestas'])
    except Exception as e:
        print(f"Error al mostrar migraciones: {e}")

if __name__ == '__main__':
    main()