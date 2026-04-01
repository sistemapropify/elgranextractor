#!/usr/bin/env python
"""
Script para diagnosticar por qué no cargan las propiedades de Propifai.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

try:
    from propifai.models import PropifaiProperty
    
    print("=== DIAGNÓSTICO DE PROPIEDADES PROPIFAI ===")
    
    # 1. Verificar si el modelo existe
    print("1. Modelo PropifaiProperty importado correctamente")
    
    # 2. Contar propiedades totales
    try:
        total_count = PropifaiProperty.objects.count()
        print(f"2. Total propiedades en tabla PropifaiProperty: {total_count}")
    except Exception as e:
        print(f"2. ERROR contando propiedades: {e}")
        print(f"   Detalle: {type(e).__name__}: {str(e)}")
    
    # 3. Contar propiedades con coordenadas
    try:
        with_coords = PropifaiProperty.objects.filter(
            coordinates__isnull=False
        ).exclude(coordinates='').count()
        print(f"3. Propiedades con coordenadas: {with_coords}")
    except Exception as e:
        print(f"3. ERROR contando propiedades con coordenadas: {e}")
    
    # 4. Verificar algunas propiedades de ejemplo
    try:
        sample_props = PropifaiProperty.objects.filter(
            coordinates__isnull=False
        ).exclude(coordinates='')[:5]
        
        print(f"4. Ejemplo de propiedades (primeras 5):")
        for i, prop in enumerate(sample_props):
            print(f"   {i+1}. ID: {prop.id}, Coordenadas: '{prop.coordinates}'")
    except Exception as e:
        print(f"4. ERROR obteniendo propiedades de ejemplo: {e}")
    
    # 5. Verificar estructura de la tabla
    try:
        print(f"5. Campos del modelo:")
        for field in PropifaiProperty._meta.fields:
            print(f"   - {field.name} ({field.get_internal_type()})")
    except Exception as e:
        print(f"5. ERROR obteniendo campos: {e}")
    
    # 6. Verificar si hay datos en la tabla
    try:
        if total_count > 0:
            first_prop = PropifaiProperty.objects.first()
            print(f"6. Primera propiedad: ID={first_prop.id}, title='{first_prop.title}'")
        else:
            print("6. La tabla PropifaiProperty está vacía")
    except Exception as e:
        print(f"6. ERROR obteniendo primera propiedad: {e}")
    
    print(f"\n=== CONCLUSIÓN ===")
    if total_count == 0:
        print("La tabla PropifaiProperty está vacía. No hay propiedades para mostrar.")
    elif with_coords == 0:
        print("Hay propiedades pero ninguna tiene coordenadas válidas.")
    else:
        print(f"Hay {with_coords} propiedades con coordenadas que deberían mostrarse en el heatmap.")
        
except ImportError as e:
    print(f"ERROR importando PropifaiProperty: {e}")
    print("Posibles causas:")
    print("1. El modelo PropifaiProperty no existe en propifai/models.py")
    print("2. Hay un error de sintaxis en el modelo")
    print("3. La aplicación 'propifai' no está en INSTALLED_APPS")
except Exception as e:
    print(f"ERROR general: {type(e).__name__}: {str(e)}")