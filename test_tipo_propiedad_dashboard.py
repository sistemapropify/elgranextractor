#!/usr/bin/env python
"""
Script para verificar los tipos de propiedad que se están mostrando en el dashboard.
"""
import os
import sys
import django

sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty
from django.db import connections

def test_property_types():
    conn = connections['propifai']
    property_type_map = {}
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name FROM property_types")
        for row in cursor.fetchall():
            property_type_map[row[0]] = row[1]
    print(f"Mapeo property_type_map: {property_type_map}")
    
    # Obtener algunas propiedades
    props = PropifaiProperty.objects.all()[:5]
    for prop in props:
        print(f"\nPropiedad ID: {prop.id}, Código: {prop.code}")
        # Obtener property_type_id desde la tabla properties
        with conn.cursor() as cursor:
            cursor.execute("SELECT property_type_id, created_by_id FROM properties WHERE id = %s", [prop.id])
            row = cursor.fetchone()
            if row:
                pt_id, cb_id = row
                tipo = property_type_map.get(pt_id, '—')
                print(f"  property_type_id: {pt_id}, tipo: {tipo}")
            else:
                print(f"  No encontrada en tabla properties")

if __name__ == '__main__':
    test_property_types()