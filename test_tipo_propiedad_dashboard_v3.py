#!/usr/bin/env python
"""
Script para verificar los tipos de propiedad en el dashboard.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty

# Simular la lógica de la vista (actualizada)
propiedades = PropifaiProperty.objects.all()
total_db = propiedades.count()
print(f"Total propiedades en DB: {total_db}")

propiedades_con_score = []
for prop in propiedades:
    # Determinar tipo de propiedad estandarizado (misma lógica que la vista)
    tipo_propiedad_valor = '—'
    # Primero intentar inferir del título
    if prop.title:
        titulo_lower = prop.title.lower()
        if any(tipo in titulo_lower for tipo in ['casa', 'house']):
            tipo_propiedad_valor = 'Casa'
        elif any(tipo in titulo_lower for tipo in ['departamento', 'apartamento', 'apartment']):
            tipo_propiedad_valor = 'Departamento'
        elif any(tipo in titulo_lower for tipo in ['terreno', 'land', 'lote']):
            tipo_propiedad_valor = 'Terreno'
        elif any(tipo in titulo_lower for tipo in ['oficina', 'office', 'local']):
            tipo_propiedad_valor = 'Oficina'
        # Si no se encontró coincidencia, verificar si hay un campo tipo_propiedad que no sea "Propiedad"
        if tipo_propiedad_valor == '—' and hasattr(prop, 'tipo_propiedad'):
            valor_tipo = prop.tipo_propiedad
            if valor_tipo and valor_tipo.lower() != 'propiedad':
                tipo_propiedad_valor = valor_tipo
    else:
        # Si no hay título, usar tipo_propiedad si existe y no es "Propiedad"
        if hasattr(prop, 'tipo_propiedad'):
            valor_tipo = prop.tipo_propiedad
            if valor_tipo and valor_tipo.lower() != 'propiedad':
                tipo_propiedad_valor = valor_tipo
    prop.property_type = tipo_propiedad_valor
    propiedades_con_score.append(prop)

# Contar tipos únicos
tipos = {}
for prop in propiedades_con_score:
    tipo = getattr(prop, 'property_type', '—')
    tipos[tipo] = tipos.get(tipo, 0) + 1

print("\nDistribucion de tipos de propiedad:")
for tipo, count in sorted(tipos.items(), key=lambda x: x[1], reverse=True):
    print(f"  {tipo}: {count}")

# Verificar si hay valores "Propiedad"
if 'Propiedad' in tipos:
    print("\nADVERTENCIA: Hay propiedades con tipo 'Propiedad' (valor por defecto)")
    # Mostrar ejemplos
    for prop in propiedades_con_score:
        if getattr(prop, 'property_type', '—') == 'Propiedad':
            print(f"  - {prop.code}: {prop.title[:80]}")
else:
    print("\nOK: No hay propiedades con tipo 'Propiedad' (bueno)")

# Mostrar algunos ejemplos
print("\nMuestra de 10 propiedades:")
for i, prop in enumerate(propiedades_con_score[:10]):
    print(f"{i+1}. Codigo: {prop.code}, Titulo: {prop.title[:50]}, Tipo: {prop.property_type}")

# Verificar si hay valores "—" (guion)
if '—' in tipos:
    print(f"\nHay {tipos['—']} propiedades con tipo indeterminado (—)")
    # Mostrar algunos titulos de esas propiedades
    count = 0
    for prop in propiedades_con_score:
        if prop.property_type == '—':
            print(f"  - {prop.code}: {prop.title[:80]}")
            count += 1
            if count >= 5:
                break