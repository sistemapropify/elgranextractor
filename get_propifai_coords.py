#!/usr/bin/env python
"""
Obtener coordenadas de propiedades de Propifai.
"""
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty

# Obtener propiedades con coordenadas no nulas
props = PropifaiProperty.objects.filter(coordinates__isnull=False)[:10]

print("Propiedades de Propifai con coordenadas:")
for prop in props:
    print(f"ID: {prop.id}, Código: {prop.code}")
    print(f"  Coordenadas: {prop.coordinates}")
    print(f"  Latitud: {prop.latitude}, Longitud: {prop.longitude}")
    print(f"  Distrito: {prop.district}")
    print(f"  Precio: {prop.price}, Área construida: {prop.built_area}")
    print()