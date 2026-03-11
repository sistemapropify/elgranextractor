#!/usr/bin/env python
"""
Test para verificar si PropifaiProperty está usando la base de datos correcta.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty

print("=== TEST DE BASE DE DATOS PROPIY ===")
print()

# Probar diferentes formas de acceder a la base de datos
print("1. Usando .objects.count() (sin especificar DB):")
try:
    count1 = PropifaiProperty.objects.count()
    print(f"   Resultado: {count1}")
except Exception as e:
    print(f"   ERROR: {e}")

print()

print("2. Usando .objects.using('propifai').count():")
try:
    count2 = PropifaiProperty.objects.using('propifai').count()
    print(f"   Resultado: {count2}")
except Exception as e:
    print(f"   ERROR: {e}")

print()

print("3. Verificar configuración del router:")
try:
    from django.db import connections
    conn = connections['propifai']
    print(f"   Conexión 'propifai' existe: {conn is not None}")
    print(f"   Configuración: {conn.settings_dict}")
except Exception as e:
    print(f"   ERROR: {e}")

print()

print("4. Probar consulta directa con .using('propifai'):")
try:
    props = PropifaiProperty.objects.using('propifai').all()[:3]
    print(f"   Obtenidas {len(list(props))} propiedades")
    for p in props:
        print(f"   - ID: {p.id}, Tipo: {p.tipo_propiedad}")
except Exception as e:
    print(f"   ERROR: {e}")

print()
print("=== TEST COMPLETADO ===")