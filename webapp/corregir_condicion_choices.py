#!/usr/bin/env python
"""
Corregir la discrepancia entre los valores de 'condicion' y los choices del modelo.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from ingestas.models import PropiedadRaw

print("=== CORRECCIÓN DE VALORES DE CONDICIÓN ===")
print("")

# 1. Verificar los choices actuales del modelo
from django.db import models
field = PropiedadRaw._meta.get_field('condicion')
choices = field.choices
print("1. CHOICES DEFINIDOS EN EL MODELO:")
for value, label in choices:
    print(f"   '{value}' -> '{label}'")

print("\n2. VALORES ACTUALES EN LA BASE DE DATOS:")
from django.db.models import Count
distribucion = PropiedadRaw.objects.values('condicion').annotate(
    count=Count('condicion')
).order_by('-count')

valores_unicos = []
for item in distribucion:
    cond = item['condicion']
    count = item['count']
    valores_unicos.append(cond)
    print(f"   '{cond}': {count} registros")

print("\n3. IDENTIFICANDO PROBLEMAS:")
problemas = []

# Verificar qué valores no están en los choices
for valor in valores_unicos:
    if valor is None:
        continue
    # Buscar si el valor está en los choices
    en_choices = any(valor == choice_value for choice_value, _ in choices)
    if not en_choices:
        problemas.append(valor)
        print(f"   ✗ '{valor}' NO está en los choices del modelo")

print("\n4. MAPEO DE CORRECCIÓN NECESARIO:")
print("   Los valores importados necesitan mapearse a los choices del modelo:")
print("   'venta' -> 'compra' (porque el modelo usa 'compra' no 'venta')")
print("   'alquiler' -> 'alquiler' (correcto)")
print("   'anticresis' -> 'no_especificado' (no hay opción para anticresis)")
print("   'no_especificado' -> 'no_especificado' (correcto)")

print("\n5. EJECUTANDO CORRECCIÓN...")

# Contar registros a actualizar
venta_count = PropiedadRaw.objects.filter(condicion='venta').count()
anticresis_count = PropiedadRaw.objects.filter(condicion='anticresis').count()
no_especificado_count = PropiedadRaw.objects.filter(condicion='no_especificado').count()

print(f"   Registros 'venta' a actualizar: {venta_count}")
print(f"   Registros 'anticresis' a actualizar: {anticresis_count}")
print(f"   Registros 'no_especificado': {no_especificado_count}")

# Preguntar si se debe proceder
print("\n¿Deseas proceder con la corrección? (s/n)")
respuesta = input().strip().lower()

if respuesta == 's':
    print("\nActualizando registros...")
    
    # Actualizar 'venta' -> 'compra'
    if venta_count > 0:
        actualizados = PropiedadRaw.objects.filter(condicion='venta').update(condicion='compra')
        print(f"   ✓ Actualizados {actualizados} registros de 'venta' a 'compra'")
    
    # Actualizar 'anticresis' -> 'no_especificado'
    if anticresis_count > 0:
        actualizados = PropiedadRaw.objects.filter(condicion='anticresis').update(condicion='no_especificado')
        print(f"   ✓ Actualizados {actualizados} registros de 'anticresis' a 'no_especificado'")
    
    print("\n✅ CORRECCIÓN COMPLETADA")
    
    # Verificar resultado
    print("\n6. VERIFICACIÓN FINAL:")
    distribucion_final = PropiedadRaw.objects.values('condicion').annotate(
        count=Count('condicion')
    ).order_by('-count')
    
    for item in distribucion_final:
        cond = item['condicion']
        count = item['count']
        print(f"   '{cond}': {count} registros")
    
    # Verificar que todos los valores estén en choices
    print("\n   Todos los valores ahora están en los choices:")
    for item in distribucion_final:
        cond = item['condicion']
        if cond is None:
            continue
        en_choices = any(cond == choice_value for choice_value, _ in choices)
        status = "✓" if en_choices else "✗"
        print(f"   {status} '{cond}' -> {'EN CHOICES' if en_choices else 'FUERA DE CHOICES'}")
    
    print("\n🎯 RECOMENDACIÓN:")
    print("   Ahora los campos 'condicion' deberían mostrarse correctamente en Django admin.")
    print("   Recarga la página del admin (Ctrl+F5) para ver los cambios.")
    
else:
    print("\n❌ CORRECCIÓN CANCELADA")
    print("   Los campos seguirán mostrándose vacíos en Django admin.")
    print("   Para corregir manualmente, puedes:")
    print("   1. Actualizar los choices del modelo para incluir 'venta' y 'anticresis'")
    print("   2. O ejecutar este script más tarde con 's'")

print("\n" + "="*60)
print("EXPLICACIÓN TÉCNICA:")
print("Django admin usa los 'choices' del modelo para:")
print("1. Validar los valores ingresados")
print("2. Mostrar etiquetas legibles en lugar de los valores crudos")
print("3. Proporcionar opciones en los formularios")
print("")
print("Cuando un valor no está en los choices, Django puede:")
print("- Mostrarlo vacío en list_display")
print("- Mostrar el valor crudo sin traducción")
print("- Causar errores de validación en formularios")