#!/usr/bin/env python
"""
Diagnóstico de conexión a base de datos Propifai.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.db import connections
from propifai.models import PropifaiProperty

def test_connection():
    """Probar conexión a la base de datos propifai."""
    print("=== DIAGNÓSTICO BASE DE DATOS PROPIFAI ===")
    
    # 1. Verificar conexión
    try:
        conn = connections['propifai']
        conn.ensure_connection()
        print("✓ Conexión a base de datos 'propifai' establecida")
        print(f"   Base de datos: {conn.settings_dict['NAME']}")
        print(f"   Host: {conn.settings_dict['HOST']}")
        print(f"   Usuario: {conn.settings_dict['USER']}")
    except Exception as e:
        print(f"✗ Error de conexión: {e}")
        return False
    
    # 2. Contar total de propiedades
    try:
        total = PropifaiProperty.objects.using('propifai').count()
        print(f"✓ Total de propiedades en tabla PropifaiProperty: {total}")
    except Exception as e:
        print(f"✗ Error al contar propiedades: {e}")
        return False
    
    # 3. Contar propiedades con coordenadas no nulas
    try:
        with_coords = PropifaiProperty.objects.using('propifai').filter(
            coordinates__isnull=False
        ).exclude(coordinates='').count()
        print(f"✓ Propiedades con coordenadas no nulas: {with_coords}")
    except Exception as e:
        print(f"✗ Error al contar coordenadas: {e}")
        return False
    
    # 4. Verificar algunos registros de ejemplo
    try:
        sample = PropifaiProperty.objects.using('propifai').filter(
            coordinates__isnull=False
        ).exclude(coordinates='')[:3]
        print("✓ Ejemplo de propiedades con coordenadas:")
        for i, prop in enumerate(sample):
            print(f"   {i+1}. ID: {prop.id}, coordinates: '{prop.coordinates}'")
    except Exception as e:
        print(f"✗ Error al obtener ejemplos: {e}")
    
    # 5. Verificar campo price
    try:
        with_price = PropifaiProperty.objects.using('propifai').filter(
            price__isnull=False
        ).exclude(price=0).count()
        print(f"✓ Propiedades con precio no nulo: {with_price}")
    except Exception as e:
        print(f"✗ Error al contar precios: {e}")
    
    # 6. Verificar campo built_area
    try:
        with_area = PropifaiProperty.objects.using('propifai').filter(
            built_area__isnull=False
        ).exclude(built_area=0).count()
        print(f"✓ Propiedades con área construida no nula: {with_area}")
    except Exception as e:
        print(f"✗ Error al contar áreas: {e}")
    
    return True

if __name__ == '__main__':
    success = test_connection()
    sys.exit(0 if success else 1)