#!/usr/bin/env python
"""
Script para aplicar migraciones falsas y forzar la sincronización del esquema.
"""

import os
import sys
import django
import subprocess

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')
django.setup()

def main():
    print("=== MIGRACIONES FALSAS PARA INGESTAS ===")
    
    # Listar migraciones
    print("\n1. Listando migraciones de 'ingestas':")
    try:
        output = subprocess.check_output(
            ['python', 'manage.py', 'showmigrations', 'ingestas'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.STDOUT,
            text=True
        )
        print(output)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.output}")
        return
    
    # Encontrar la última migración no aplicada
    print("\n2. Aplicando migración más reciente con --fake:")
    try:
        output = subprocess.check_output(
            ['python', 'manage.py', 'migrate', 'ingestas', '--fake'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.STDOUT,
            text=True
        )
        print(output)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.output}")
    
    # Aplicar migración real (sin --fake) para asegurar esquema
    print("\n3. Aplicando migración real (sin --fake):")
    try:
        output = subprocess.check_output(
            ['python', 'manage.py', 'migrate', 'ingestas'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.STDOUT,
            text=True
        )
        print(output)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.output}")
    
    # Verificar estado final
    print("\n4. Estado final de migraciones:")
    try:
        output = subprocess.check_output(
            ['python', 'manage.py', 'showmigrations', 'ingestas'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.STDOUT,
            text=True
        )
        print(output)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.output}")
    
    print("\n=== COMPLETADO ===")
    print("Reinicia el servidor Django y prueba el admin.")

if __name__ == '__main__':
    main()