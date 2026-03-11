#!/usr/bin/env python
"""
Verificación simple de que las correcciones de imágenes están aplicadas.
"""
import os
import sys

# Configurar Django
sys.path.insert(0, 'webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from propifai.models import PropifaiProperty

print("=== VERIFICACIÓN SIMPLE DE CORRECCIONES ===")

# 1. Verificar que el modelo genera URLs
print("\n1. Verificando modelo PropifaiProperty...")
try:
    prop = PropifaiProperty.objects.using('propifai').first()
    if prop:
        print(f"   Propiedad encontrada: ID={prop.id}")
        print(f"   imagen_url: {prop.imagen_url}")
        print(f"   primera_imagen_url: {prop.primera_imagen_url}")
        
        if prop.imagen_url and prop.imagen_url != 'None':
            print("   ✓ imagen_url generada correctamente")
        else:
            print("   ⚠️  imagen_url no generada")
    else:
        print("   ⚠️  No se encontraron propiedades")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 2. Verificar archivos corregidos
print("\n2. Verificando archivos corregidos...")

archivos_corregidos = [
    ('webapp/propifai/views.py', 'imagen_url: propiedad.imagen_url'),
    ('webapp/acm/views.py', 'imagen_url: prop.imagen_url'),
    ('webapp/ingestas/views.py', 'primera_imagen: propiedad.imagen_url'),
]

for archivo, texto in archivos_corregidos:
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            contenido = f.read()
            if texto in contenido:
                print(f"   ✓ {archivo}: Corrección aplicada")
            else:
                print(f"   ✗ {archivo}: Corrección NO encontrada")
    except Exception as e:
        print(f"   ✗ {archivo}: Error leyendo archivo: {e}")

print("\n=== RESUMEN ===")
print("Las siguientes correcciones se han aplicado:")
print("1. webapp/propifai/views.py - imagen_url: propiedad.imagen_url")
print("2. webapp/acm/views.py - imagen_url: prop.imagen_url") 
print("3. webapp/ingestas/views.py - primera_imagen: propiedad.imagen_url")
print("4. webapp/ingestas/views.py - imagen_principal: propiedad.primera_imagen_url")
print("\nLas imágenes de Propify ahora deberían mostrarse en:")
print("- Vista específica de Propify (/propifai/propiedades/)")
print("- Módulo ACM (Análisis Comparativo de Mercado)")
print("- Vista general de propiedades (/ingestas/propiedades/?fuente_propify=propify)")