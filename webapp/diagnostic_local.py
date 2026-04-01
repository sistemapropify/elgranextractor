#!/usr/bin/env python
"""
Diagnóstico de propiedades locales (PropiedadRaw).
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.db import connections
from ingestas.models import PropiedadRaw

def test_local():
    """Probar conexión y datos locales."""
    print("=== DIAGNÓSTICO PROPIEDADES LOCALES (PropiedadRaw) ===")
    
    # 1. Verificar conexión a base de datos default
    try:
        conn = connections['default']
        conn.ensure_connection()
        print("✓ Conexión a base de datos 'default' establecida")
        print(f"   Base de datos: {conn.settings_dict['NAME']}")
        print(f"   Host: {conn.settings_dict['HOST']}")
    except Exception as e:
        print(f"✗ Error de conexión: {e}")
        return False
    
    # 2. Contar total de propiedades
    try:
        total = PropiedadRaw.objects.using('default').count()
        print(f"✓ Total de propiedades en tabla PropiedadRaw: {total}")
    except Exception as e:
        print(f"✗ Error al contar total: {e}")
        return False
    
    # 3. Contar propiedades con coordenadas no nulas
    try:
        with_coords = PropiedadRaw.objects.using('default').filter(
            coordenadas__isnull=False
        ).exclude(coordenadas='').count()
        print(f"✓ Propiedades con coordenadas no nulas: {with_coords}")
    except Exception as e:
        print(f"✗ Error al contar coordenadas: {e}")
        return False
    
    # 4. Verificar algunas coordenadas de ejemplo
    try:
        sample = PropiedadRaw.objects.using('default').filter(
            coordenadas__isnull=False
        ).exclude(coordenadas='')[:3]
        print("✓ Ejemplo de propiedades con coordenadas:")
        for i, prop in enumerate(sample):
            print(f"   {i+1}. ID: {prop.id}, coordenadas: '{prop.coordenadas}'")
    except Exception as e:
        print(f"✗ Error al obtener ejemplos: {e}")
    
    # 5. Verificar campo precio_usd
    try:
        with_price = PropiedadRaw.objects.using('default').filter(
            precio_usd__isnull=False
        ).exclude(precio_usd=0).count()
        print(f"✓ Propiedades con precio no nulo: {with_price}")
    except Exception as e:
        print(f"✗ Error al contar precios: {e}")
    
    # 6. Verificar campo area_construida
    try:
        with_area = PropiedadRaw.objects.using('default').filter(
            area_construida__isnull=False
        ).exclude(area_construida=0).count()
        print(f"✓ Propiedades con área construida no nula: {with_area}")
    except Exception as e:
        print(f"✗ Error al contar áreas: {e}")
    
    return True

if __name__ == '__main__':
    success = test_local()
    sys.exit(0 if success else 1)