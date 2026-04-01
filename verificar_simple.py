#!/usr/bin/env python
"""
Verificación simple del problema de Propify.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty

print("=== VERIFICACIÓN SIMPLE DE PROPIEDADES PROPIY ===")
print()

# 1. Verificar base de datos directamente
print("1. Verificando base de datos Propifai...")
try:
    count = PropifaiProperty.objects.using('propifai').count()
    print(f"   Total propiedades en DB Propifai: {count}")
    
    if count > 0:
        # Mostrar algunas propiedades
        props = PropifaiProperty.objects.using('propifai').all()[:5]
        for i, p in enumerate(props):
            print(f"   Propiedad {i+1}:")
            print(f"     ID: {p.id}")
            print(f"     Tipo: {p.tipo_propiedad}")
            print(f"     Precio: {p.price}")
            print(f"     Coordenadas: {p.coordinates}")
            print(f"     Lat: {p.latitude}")
            print(f"     Lng: {p.longitude}")
            print()
    else:
        print("   ¡NO HAY PROPIEDADES EN LA BASE DE DATOS PROPIY!")
        
except Exception as e:
    print(f"   ERROR al acceder a DB Propifai: {e}")
    import traceback
    traceback.print_exc()

print()

# 2. Verificar si el modelo tiene los campos correctos
print("2. Verificando estructura del modelo...")
try:
    from django.db import connection
    with connection.cursor() as cursor:

        columns = [col[0] for col in cursor.description]
        print(f"   Columnas en tabla dbo.properties: {len(columns)}")
        print(f"   Primeras 10 columnas: {columns[:10]}")
except Exception as e:
    print(f"   ERROR al verificar estructura: {e}")

print()
print("=== VERIFICACIÓN COMPLETADA ===")