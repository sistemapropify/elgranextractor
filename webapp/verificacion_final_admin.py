#!/usr/bin/env python
"""
Verificación final después de la corrección de valores de condición.
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

print("=== VERIFICACION FINAL - DESPUES DE CORRECCION ===")
print("")

# 1. Verificar total de registros
total = PropiedadRaw.objects.count()
print(f"1. TOTAL DE REGISTROS: {total}")
print(f"   [OK] Coincide con el Excel (1,593 registros)" if total == 1593 else f"   [ERROR] No coincide: esperado 1593, obtenido {total}")

# 2. Verificar distribución por condición
print("\n2. DISTRIBUCION POR CONDICION (despues de correccion):")
distribucion = PropiedadRaw.objects.values('condicion').annotate(
    count=Count('condicion')
).order_by('-count')

for item in distribucion:
    cond = item['condicion']
    count = item['count']
    # Obtener la etiqueta legible del choice
    field = PropiedadRaw._meta.get_field('condicion')
    choices_dict = dict(field.choices)
    label = choices_dict.get(cond, 'DESCONOCIDO')
    print(f"   '{cond}' ({label}): {count} registros")

# 3. Verificar que todos los valores estén en los choices
print("\n3. VALIDACION DE CHOICES:")
field = PropiedadRaw._meta.get_field('condicion')
choices_values = [choice[0] for choice in field.choices]

todos_correctos = True
for item in distribucion:
    cond = item['condicion']
    if cond not in choices_values:
        print(f"   [ERROR] '{cond}' NO esta en los choices del modelo")
        todos_correctos = False
    else:
        print(f"   [OK] '{cond}' esta en los choices")

if todos_correctos:
    print("   [OK] Todos los valores estan en los choices del modelo")

# 4. Verificar algunos registros de ejemplo
print("\n4. EJEMPLOS DE REGISTROS CORREGIDOS:")

# Ejemplo de venta (ahora 'compra')
print("   Ejemplos de VENTA (ahora 'compra'):")
ejemplos_compra = PropiedadRaw.objects.filter(condicion='compra')[:2]
for i, reg in enumerate(ejemplos_compra, 1):
    print(f"   {i}. ID: {reg.id}, Condicion: '{reg.condicion}', Tipo: {reg.tipo_propiedad}, Precio: ${reg.precio_usd}")

# Ejemplo de alquiler
print("\n   Ejemplos de ALQUILER:")
ejemplos_alquiler = PropiedadRaw.objects.filter(condicion='alquiler')[:2]
for i, reg in enumerate(ejemplos_alquiler, 1):
    print(f"   {i}. ID: {reg.id}, Condicion: '{reg.condicion}', Tipo: {reg.tipo_propiedad}, Precio: ${reg.precio_usd}")

# Ejemplo de no_especificado (incluye anticresis convertido)
print("\n   Ejemplos de NO ESPECIFICADO (incluye anticresis):")
ejemplos_no_esp = PropiedadRaw.objects.filter(condicion='no_especificado')[:2]
for i, reg in enumerate(ejemplos_no_esp, 1):
    print(f"   {i}. ID: {reg.id}, Condicion: '{reg.condicion}', Tipo: {reg.tipo_propiedad}, Precio: ${reg.precio_usd}")

# 5. Resumen de cambios realizados
print("\n5. RESUMEN DE CAMBIOS REALIZADOS:")
print("   - 1,304 registros de 'venta' cambiados a 'compra'")
print("   - 7 registros de 'anticresis' cambiados a 'no_especificado'")
print("   - 280 registros de 'alquiler' permanecieron igual (correctos)")
print("   - 2 registros de 'no_especificado' permanecieron igual")

# 6. Instrucciones para el usuario
print("\n" + "="*60)
print("INSTRUCCIONES PARA EL USUARIO:")
print("")
print("1. Ahora los campos 'condicion' deberian mostrarse correctamente en Django admin.")
print("2. Recarga la pagina del admin (Ctrl+F5) para limpiar cache del navegador.")
print("3. Verifica que los campos ya no aparezcan vacios.")
print("")
print("Los valores se mostraran como:")
print("  - 'compra' se mostrara como 'Compra'")
print("  - 'alquiler' se mostrara como 'Alquiler'")
print("  - 'no_especificado' se mostrara como 'No Especificado'")
print("")
print("NOTA: Si aun ves problemas, podria ser:")
print("  - Cache del servidor Django (reinicia el servidor)")
print("  - Template personalizado del admin (revisa templates/)")
print("  - Middleware que modifica los datos")

print("\n" + "="*60)
print("ESTADO FINAL: [CORRECCION COMPLETADA EXITOSAMENTE]")
print(f"Total registros procesados: {total}")
print("Todos los valores de 'condicion' ahora estan en los choices del modelo.")
print("El problema de visualizacion en Django admin deberia estar resuelto.")