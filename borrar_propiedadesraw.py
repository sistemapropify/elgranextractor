#!/usr/bin/env python
"""
Script para borrar todos los registros de PropiedadRaw.
"""
import os
import sys

# Agregar el directorio webapp al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
import django
django.setup()

from ingestas.models import PropiedadRaw

def main():
    # Contar registros antes
    count_before = PropiedadRaw.objects.count()
    print(f"Registros de PropiedadRaw antes de borrar: {count_before}")
    
    if count_before == 0:
        print("No hay registros para borrar.")
        return
    
    # Preguntar confirmación (opcional, pero por seguridad)
    confirm = input(f"¿Estás seguro de borrar {count_before} registros? (sí/no): ")
    if confirm.lower() not in ('sí', 'si', 's', 'yes', 'y'):
        print("Operación cancelada.")
        return
    
    # Borrar todos los registros
    deleted_count, _ = PropiedadRaw.objects.all().delete()
    print(f"Borrados {deleted_count} registros de PropiedadRaw.")
    
    # Verificar
    count_after = PropiedadRaw.objects.count()
    print(f"Registros de PropiedadRaw después de borrar: {count_after}")

if __name__ == '__main__':
    main()