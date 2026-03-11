#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty

print("=== CAMPOS DISPONIBLES EN PROPIFAIPROPERTY ===")
print()

# Obtener una propiedad de ejemplo
prop = PropifaiProperty.objects.first()
if prop:
    print("Campos de la primera propiedad:")
    for field in prop._meta.fields:
        field_name = field.name
        value = getattr(prop, field_name, None)
        print(f"  {field_name}: {value}")
else:
    print("No hay propiedades en la base de datos")

print()
print("=== BUSCANDO TÉRMINOS RELACIONADOS CON TERRENOS ===")
print()

# Buscar en varios campos posibles
campos_posibles = ['zoning', 'description', 'title', 'real_address', 'exact_address', 'unit_location']

props = PropifaiProperty.objects.filter(coordinates__isnull=False).exclude(coordinates='')[:20]

for prop in props:
    print(f"\nPropiedad ID {prop.id}:")
    for campo in campos_posibles:
        valor = getattr(prop, campo, None)
        if valor:
            valor_str = str(valor).lower()
            # Buscar términos de terreno
            if any(term in valor_str for term in ['terreno', 'terrenos', 'lote', 'parcela', 'land', 'lot', 'plot', 'ground', 'solar', 'vacant']):
                print(f"  {campo}: '{valor}' (¡POSIBLE TERRENO!)")
            else:
                # Mostrar solo si no está vacío
                if len(str(valor).strip()) > 0:
                    print(f"  {campo}: '{valor}'")