#!/usr/bin/env python
"""
Script para verificar la importación de propiedadesraw.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from ingestas.models import PropiedadRaw

print("=== VERIFICACIÓN DE IMPORTACIÓN DE PROPIEDADESRAW ===")
print("")

# 1. Contar registros totales
total = PropiedadRaw.objects.count()
print(f"1. Total de registros en PropiedadRaw: {total}")

if total == 0:
    print("   ⚠️  La tabla está vacía. La importación puede haber fallado.")
    sys.exit(1)

# 2. Verificar campo 'condicion'
print("\n2. Distribución del campo 'condicion':")
condiciones = PropiedadRaw.objects.values_list('condicion', flat=True).distinct()
conteo_condiciones = {}

for cond in condiciones:
    if cond:
        count = PropiedadRaw.objects.filter(condicion=cond).count()
        conteo_condiciones[cond] = count

if conteo_condiciones:
    for cond, count in sorted(conteo_condiciones.items()):
        porcentaje = (count / total) * 100
        print(f"   - '{cond}': {count} registros ({porcentaje:.1f}%)")
else:
    print("   ⚠️  No hay valores en el campo 'condicion'.")

# 3. Verificar valores específicos esperados
print("\n3. Valores específicos en 'condicion':")
valores_esperados = ['venta', 'alquiler', 'anticresis', 'no_especificado']
for valor in valores_esperados:
    count = PropiedadRaw.objects.filter(condicion=valor).count()
    print(f"   - '{valor}': {count} registros")

# 4. Verificar campos importantes no nulos
print("\n4. Completitud de datos:")
campos_importantes = ['tipo_propiedad', 'precio_usd', 'departamento', 'distrito']
for campo in campos_importantes:
    try:
        count_no_nulos = PropiedadRaw.objects.exclude(**{f'{campo}__isnull': True}).exclude(**{campo: ''}).count()
        porcentaje = (count_no_nulos / total) * 100
        print(f"   - '{campo}': {count_no_nulos}/{total} ({porcentaje:.1f}%) no nulos")
    except:
        print(f"   - '{campo}': Error al verificar")

# 5. Mostrar algunos registros de ejemplo
print("\n5. Registros de ejemplo (primeros 3):")
ejemplos = PropiedadRaw.objects.all()[:3]
for i, prop in enumerate(ejemplos, 1):
    print(f"\n   Registro {i}:")
    print(f"     ID: {prop.id}")
    print(f"     Tipo: {prop.tipo_propiedad}")
    print(f"     Condición: {prop.condicion}")
    print(f"     Precio USD: {prop.precio_usd}")
    print(f"     Departamento: {prop.departamento}")
    print(f"     Distrito: {prop.distrito}")

print("\n" + "="*60)
print("VERIFICACIÓN COMPLETADA.")
if total > 0:
    print(f"✅ Importación exitosa con {total} registros.")
else:
    print("❌ La importación falló o la tabla está vacía.")