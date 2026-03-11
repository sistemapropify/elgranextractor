#!/usr/bin/env python
"""
Script para borrar todos los registros de la tabla PropiedadRaw.
"""
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw

print("=== Borrando registros de PropiedadRaw ===")
count = PropiedadRaw.objects.count()
print(f"Total registros antes: {count}")

if count > 0:
    confirm = input(f"¿Estás seguro de borrar {count} registros? (s/n): ")
    if confirm.lower() == 's':
        deleted = PropiedadRaw.objects.all().delete()
        print(f"Registros borrados: {deleted[0]}")
    else:
        print("Operación cancelada.")
else:
    print("No hay registros para borrar.")