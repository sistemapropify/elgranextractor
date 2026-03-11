#!/usr/bin/env python
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from cuadrantizacion.models import ZonaValor

zonas = ZonaValor.objects.all()
print('Total zonas:', zonas.count())
for z in zonas:
    print(f'ID: {z.id}, Nombre: {z.nombre_zona}, Nivel: {z.nivel}, Padre: {z.parent_id if z.parent else None}, Coordenadas: {len(z.coordenadas) if z.coordenadas else 0} puntos')