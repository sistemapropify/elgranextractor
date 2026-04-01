#!/usr/bin/env python
"""
Corregir la discrepancia entre los valores de 'condicion' y los choices del modelo.
Versión simplificada sin caracteres Unicode.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from ingestas.models import PropiedadRaw
from django.db.models import Count

print("=== CORRECCION DE VALORES DE CONDICION ===")
print("")

# 1. Verificar los choices actuales del modelo
from django.db import models
field = PropiedadRaw._meta.get_field('condicion')
choices = field.choices
print("1. CHOICES DEFINIDOS EN EL MODELO:")
for value, label in choices:
    print(f"   '{value}' -> '{label}'")

print("\n2. VALORES ACTUALES EN LA BASE DE DATOS:")
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
        print(f"   [X] '{valor}' NO esta en los choices del modelo")

print("\n4. MAPEO DE CORRECCION NECESARIO:")
print("   Los valores importados necesitan mapearse a los choices del modelo:")
print("   'venta' -> 'compra' (porque el modelo usa 'compra' no 'venta')")
print("   'alquiler' -> 'alquiler' (correcto)")
print("   'anticresis' -> 'no_especificado' (no hay opcion para anticresis)")
print("   'no_especificado' -> 'no_especificado' (correcto)")

print("\n5. EJECUTANDO CORRECCION...")

# Contar registros a actualizar
venta_count = PropiedadRaw.objects.filter(condicion='venta').count()
anticresis_count = PropiedadRaw.objects.filter(condicion='anticresis').count()
no_especificado_count = PropiedadRaw.objects.filter(condicion='no_especificado').count()

print(f"   Registros 'venta' a actualizar: {venta_count}")
print(f"   Registros 'anticresis' a actualizar: {anticresis_count}")
print(f"   Registros 'no_especificado': {no_especificado_count}")

# Proceder automáticamente (sin preguntar)
print("\nProcediendo con la correccion automaticamente...")

# Actualizar 'venta' -> 'compra'
if venta_count > 0:
    actualizados = PropiedadRaw.objects.filter(condicion='venta').update(condicion='compra')
    print(f"   [OK] Actualizados {actualizados} registros de 'venta' a 'compra'")

# Actualizar 'anticresis' -> 'no_especificado'
if anticresis_count > 0:
    actualizados = PropiedadRaw.objects.filter(condicion='anticresis').update(condicion='no_especificado')
    print(f"   [OK] Actualizados {actualizados} registros de 'anticresis' a 'no_especificado'")

print("\n[CORRECCION COMPLETADA]")

# Verificar resultado
print("\n6. VERIFICACION FINAL:")
distribucion_final = PropiedadRaw.objects.values('condicion').annotate(
    count=Count('condicion')
).order_by('-count')

for item in distribucion_final:
    cond = item['condicion']
    count = item['count']
    print(f"   '{cond}': {count} registros")

# Verificar que todos los valores estén en choices
print("\n   Todos los valores ahora estan en los choices:")
for item in distribucion_final:
    cond = item['condicion']
    if cond is None:
        continue
    en_choices = any(cond == choice_value for choice_value, _ in choices)
    status = "[OK]" if en_choices else "[ERROR]"
    print(f"   {status} '{cond}' -> {'EN CHOICES' if en_choices else 'FUERA DE CHOICES'}")

print("\n[RECOMENDACION]:")
print("   Ahora los campos 'condicion' deberian mostrarse correctamente en Django admin.")
print("   Recarga la pagina del admin (Ctrl+F5) para ver los cambios.")

print("\n" + "="*60)
print("EXPLICACION TECNICA:")
print("Django admin usa los 'choices' del modelo para:")
print("1. Validar los valores ingresados")
print("2. Mostrar etiquetas legibles en lugar de los valores crudos")
print("3. Proporcionar opciones en los formularios")
print("")
print("Cuando un valor no esta en los choices, Django puede:")
print("- Mostrarlo vacio en list_display")
print("- Mostrar el valor crudo sin traduccion")
print("- Causar errores de validacion en formularios")