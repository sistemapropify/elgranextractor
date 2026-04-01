#!/usr/bin/env python
"""
Script para verificar el campo property_type_id usando el ORM de Django.
"""
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty

# Inspeccionar campos del modelo
print("Campos de PropifaiProperty:")
for field in PropifaiProperty._meta.fields:
    print(f"  {field.name} ({field.__class__.__name__})")
    if field.is_relation:
        print(f"    -> Relación con {field.related_model.__name__}")

# Buscar campos que contengan 'type' o 'tipo'
print("\nCampos relacionados con tipo:")
for field in PropifaiProperty._meta.fields:
    if 'type' in field.name or 'tipo' in field.name:
        print(f"  {field.name} ({field.__class__.__name__})")
        if field.is_relation:
            print(f"    -> Relación con {field.related_model.__name__}")

# Verificar si hay un campo property_type_id
if hasattr(PropifaiProperty, 'property_type_id'):
    print("\nproperty_type_id existe como campo.")
else:
    print("\nproperty_type_id NO existe como campo.")

# Verificar si hay un campo property_type (ForeignKey)
if hasattr(PropifaiProperty, 'property_type'):
    print("property_type existe como campo.")
else:
    print("property_type NO existe como campo.")

# Probar con una instancia
prop = PropifaiProperty.objects.first()
if prop:
    print(f"\nPropiedad ejemplo: {prop.code}")
    # Listar todos los atributos que contengan 'type' o 'tipo'
    for attr in dir(prop):
        if 'type' in attr.lower() or 'tipo' in attr.lower():
            try:
                val = getattr(prop, attr)
                if not callable(val) or attr == 'tipo_propiedad':
                    print(f"  {attr}: {val}")
            except:
                pass

# Verificar valores de property_type_id en algunas propiedades
print("\nValores de property_type_id en las primeras 10 propiedades:")
for p in PropifaiProperty.objects.all()[:10]:
    if hasattr(p, 'property_type_id'):
        print(f"  {p.code}: property_type_id = {p.property_type_id}")
    else:
        print(f"  {p.code}: no tiene property_type_id")

# Si existe una relación, intentar acceder al nombre del tipo
print("\nIntentando acceder a property_type (relación):")
for p in PropifaiProperty.objects.all()[:5]:
    try:
        if hasattr(p, 'property_type') and p.property_type:
            print(f"  {p.code}: property_type = {p.property_type}")
            # Si es un objeto, mostrar su nombre
            if hasattr(p.property_type, 'name'):
                print(f"    -> name: {p.property_type.name}")
    except Exception as e:
        print(f"  {p.code}: error: {e}")