#!/usr/bin/env python
"""
Verificar EXACTAMENTE qué hay en la base de datos para entender el problema del admin.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from ingestas.models import PropiedadRaw

print("=== VERIFICACIÓN DETALLADA DE LA BASE DE DATOS ===")
print("")

# 1. Contar total
total = PropiedadRaw.objects.count()
print(f"1. TOTAL DE REGISTROS: {total}")

# 2. Contar por condición
print("\n2. DISTRIBUCIÓN POR CONDICIÓN:")
from django.db.models import Count, Q
distribucion = PropiedadRaw.objects.values('condicion').annotate(
    count=Count('condicion')
).order_by('-count')

for item in distribucion:
    cond = item['condicion']
    count = item['count']
    if cond is None or cond == '':
        cond = 'VACÍO/NULL'
    print(f"   '{cond}': {count} registros")

# 3. Verificar registros con condicion vacía/nula
print("\n3. REGISTROS CON CONDICIÓN VACÍA O NULA:")
vacios = PropiedadRaw.objects.filter(Q(condicion__isnull=True) | Q(condicion=''))
print(f"   Total vacíos/nulos: {vacios.count()}")

if vacios.count() > 0:
    print("   Primeros 5 registros vacíos:")
    for i, reg in enumerate(vacios[:5], 1):
        print(f"   {i}. ID: {reg.id}, Tipo: {reg.tipo_propiedad}, Precio: {reg.precio_usd}")

# 4. Mostrar ejemplos de cada tipo
print("\n4. EJEMPLOS DE REGISTROS POR TIPO:")

# Alquiler
alquileres = PropiedadRaw.objects.filter(condicion='alquiler')[:3]
print(f"   ALQUILER (total: {PropiedadRaw.objects.filter(condicion='alquiler').count()}):")
for i, reg in enumerate(alquileres, 1):
    print(f"     {i}. ID: {reg.id}, Tipo: {reg.tipo_propiedad}, Precio: ${reg.precio_usd}, Depto: {reg.departamento}")

# Venta
ventas = PropiedadRaw.objects.filter(condicion='venta')[:3]
print(f"\n   VENTA (total: {PropiedadRaw.objects.filter(condicion='venta').count()}):")
for i, reg in enumerate(ventas, 1):
    print(f"     {i}. ID: {reg.id}, Tipo: {reg.tipo_propiedad}, Precio: ${reg.precio_usd}, Depto: {reg.departamento}")

# Anticresis
anticresis = PropiedadRaw.objects.filter(condicion='anticresis')[:3]
print(f"\n   ANTICRESIS (total: {PropiedadRaw.objects.filter(condicion='anticresis').count()}):")
for i, reg in enumerate(anticresis, 1):
    print(f"     {i}. ID: {reg.id}, Tipo: {reg.tipo_propiedad}, Precio: ${reg.precio_usd}, Depto: {reg.departamento}")

# 5. Verificar si hay problemas con otros campos
print("\n5. PROBLEMAS COMUNES EN IMPORTACIÓN:")
# Campos requeridos que podrían estar vacíos
campos_problematicos = ['fuente_excel', 'tipo_propiedad', 'departamento']
for campo in campos_problematicos:
    vacios_campo = PropiedadRaw.objects.filter(**{f'{campo}__isnull': True}).count()
    print(f"   - {campo} vacío: {vacios_campo} registros")

# 6. Sugerencias
print("\n" + "="*60)
print("DIAGNÓSTICO:")

# Recalcular vacíos para condición
vacios_condicion = PropiedadRaw.objects.filter(Q(condicion__isnull=True) | Q(condicion='')).count()

if total == 0:
    print("[ERROR] LA TABLA ESTÁ COMPLETAMENTE VACÍA")
    print("   La importación falló completamente.")
elif PropiedadRaw.objects.filter(condicion='venta').count() == 0:
    print("[ADVERTENCIA] NO HAY REGISTROS DE VENTA")
    print("   Todos los registros de venta pueden tener problemas.")
elif vacios_condicion > 0:
    print(f"[ADVERTENCIA] HAY {vacios_condicion} REGISTROS CON CONDICIÓN VACÍA")
    print("   Estos aparecerán como vacíos en el admin.")
else:
    print("[OK] LA BASE DE DATOS PARECE CORRECTA")
    print("   Si ves problemas en el admin, podría ser cache o visualización.")

print("\nRecomendación: Revisa directamente en el admin los IDs mencionados arriba.")