#!/usr/bin/env python
"""
Script para verificar los campos del modelo PropiedadRaw
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw

print("=== Campos de PropiedadRaw ===")
for field in PropiedadRaw._meta.get_fields():
    if hasattr(field, 'name'):
        print(f"- {field.name}: {field.__class__.__name__}")

print("\n=== Verificando consultas ===")
# Verificar total de registros
total = PropiedadRaw.objects.using('default').count()
print(f"Total registros en base local: {total}")

# Verificar registros sin coordenadas
sin_coordenadas = PropiedadRaw.objects.using('default').filter(
    coordenadas__isnull=True
).count()
print(f"Registros sin coordenadas (isnull): {sin_coordenadas}")

sin_coordenadas_vacio = PropiedadRaw.objects.using('default').filter(
    coordenadas=''
).count()
print(f"Registros con coordenadas vacías: {sin_coordenadas_vacio}")

# Verificar registros sin precio
sin_precio = PropiedadRaw.objects.using('default').filter(
    precio_usd__isnull=True
).count()
print(f"Registros sin precio (isnull): {sin_precio}")

# Verificar registros con precio 0
precio_cero = PropiedadRaw.objects.using('default').filter(
    precio_usd=0
).count()
print(f"Registros con precio 0: {precio_cero}")

# Verificar registros sin área
sin_area = PropiedadRaw.objects.using('default').filter(
    area_construida__isnull=True
).count()
print(f"Registros sin área construida (isnull): {sin_area}")

# Verificar registros con área 0
area_cero = PropiedadRaw.objects.using('default').filter(
    area_construida=0
).count()
print(f"Registros con área construida 0: {area_cero}")

# Verificar algunos registros de ejemplo
print("\n=== Ejemplos de registros ===")
if total > 0:
    ejemplo = PropiedadRaw.objects.using('default').first()
    print(f"Primer registro ID: {ejemplo.id}")
    print(f"Coordenadas: '{ejemplo.coordenadas}'")
    print(f"Precio USD: {ejemplo.precio_usd}")
    print(f"Área construida: {ejemplo.area_construida}")
    print(f"Descripción: {ejemplo.descripcion[:50] if ejemplo.descripcion else 'N/A'}...")