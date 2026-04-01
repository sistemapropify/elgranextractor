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
from django.db.models import Count, Avg, Sum, F, Q
from django.db.models.functions import Coalesce
from django.db.models import FloatField, ExpressionWrapper

# Simular la lógica de la vista
propiedades = PropifaiProperty.objects.all()
total_db = propiedades.count()
print(f"Total propiedades en DB: {total_db}")

# Calcular completitud para cada propiedad
campos_clave = [
    'exact_address', 'coordinates', 'land_area', 'built_area', 'price',
    'bedrooms', 'bathrooms', 'description', 'district', 'title'
]

propiedades_con_score = []
for i, prop in enumerate(propiedades):
    completos = 0
    faltantes = []
    for campo in campos_clave:
        valor = getattr(prop, campo, None)
        if valor not in (None, '', 0):
            completos += 1
        else:
            faltantes.append(campo)
    score = int((completos / len(campos_clave)) * 100) if campos_clave else 0
    prop.completitud_score = score
    prop.campos_faltantes = faltantes
    
    # Determinar tipo de propiedad estandarizado
    tipo_propiedad_valor = '—'
    if hasattr(prop, 'tipo_propiedad'):
        tipo_propiedad_valor = prop.tipo_propiedad or '—'
    elif prop.title:
        # Intentar extraer tipo del título
        titulo_lower = prop.title.lower()
        if any(tipo in titulo_lower for tipo in ['casa', 'house']):
            tipo_propiedad_valor = 'Casa'
        elif any(tipo in titulo_lower for tipo in ['departamento', 'apartamento', 'apartment']):
            tipo_propiedad_valor = 'Departamento'
        elif any(tipo in titulo_lower for tipo in ['terreno', 'land', 'lote']):
            tipo_propiedad_valor = 'Terreno'
        elif any(tipo in titulo_lower for tipo in ['oficina', 'office', 'local']):
            tipo_propiedad_valor = 'Oficina'
        else:
            tipo_propiedad_valor = '—'
    prop.property_type = tipo_propiedad_valor
    propiedades_con_score.append(prop)

# Contar tipos únicos
tipos = {}
for prop in propiedades_con_score:
    tipo = getattr(prop, 'property_type', '—')
    tipos[tipo] = tipos.get(tipo, 0) + 1

print("\nDistribución de tipos de propiedad:")
for tipo, count in sorted(tipos.items(), key=lambda x: x[1], reverse=True):
    print(f"  {tipo}: {count}")

# Verificar si hay valores "Propiedad"
if 'Propiedad' in tipos:
    print("\n⚠️  ADVERTENCIA: Hay propiedades con tipo 'Propiedad' (valor por defecto)")
    # Mostrar ejemplos
    for prop in propiedades_con_score:
        if getattr(prop, 'property_type', '—') == 'Propiedad':
            print(f"  - {prop.code}: {prop.title[:80]}")
else:
    print("\n✅ No hay propiedades con tipo 'Propiedad' (bueno)")

# Mostrar algunos ejemplos
print("\nMuestra de 10 propiedades:")
for i, prop in enumerate(propiedades_con_score[:10]):
    print(f"{i+1}. Código: {prop.code}, Título: {prop.title[:50]}, Tipo: {prop.property_type}")

# Verificar si hay valores "—" (guión)
if '—' in tipos:
    print(f"\n⚠️  Hay {tipos['—']} propiedades con tipo indeterminado (—)")
    # Mostrar algunos títulos de esas propiedades
    count = 0
    for prop in propiedades_con_score:
        if prop.property_type == '—':
            print(f"  - {prop.code}: {prop.title[:80]}")
            count += 1
            if count >= 5:
                break