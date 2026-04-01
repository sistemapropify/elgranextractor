#!/usr/bin/env python
"""
Verificar si el modelo PropifaiProperty tiene campos property_type_id y created_by_id.
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

# Verificar si existen property_type_id y created_by_id
has_pt = hasattr(PropifaiProperty, 'property_type_id')
has_cb = hasattr(PropifaiProperty, 'created_by_id')
print(f"\nproperty_type_id en modelo: {has_pt}")
print(f"created_by_id en modelo: {has_cb}")

# Probar con una instancia
prop = PropifaiProperty.objects.first()
if prop:
    print(f"\nPrimera propiedad: {prop.code}")
    print(f"  property_type_id: {getattr(prop, 'property_type_id', 'NO ATTR')}")
    print(f"  created_by_id: {getattr(prop, 'created_by_id', 'NO ATTR')}")
    print(f"  assigned_agent_id: {getattr(prop, 'assigned_agent_id', 'NO ATTR')}")
    # Intentar acceder a través de _meta
    for field in PropifaiProperty._meta.fields:
        if field.name in ['property_type_id', 'created_by_id', 'assigned_agent_id']:
            print(f"  {field.name} valor: {getattr(prop, field.name)}")