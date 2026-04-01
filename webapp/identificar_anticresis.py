#!/usr/bin/env python
"""
Identificar qué registros con 'no_especificado' eran originalmente 'anticresis'.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from ingestas.models import PropiedadRaw

print("=== IDENTIFICANDO REGISTROS ANTICRESIS ===")
print("")

# 1. Verificar todos los registros con 'no_especificado'
print("1. REGISTROS CON 'no_especificado':")
registros_no_esp = PropiedadRaw.objects.filter(condicion='no_especificado')

if registros_no_esp.count() == 0:
    print("   No hay registros con 'no_especificado'")
else:
    print(f"   Total: {registros_no_esp.count()} registros")
    print("")
    print("   Lista completa:")
    for i, reg in enumerate(registros_no_esp, 1):
        print(f"   {i}. ID: {reg.id}, Tipo: {reg.tipo_propiedad}, Precio: ${reg.precio_usd}, Depto: {reg.departamento}")

# 2. Intentar identificar cuáles podrían ser 'anticresis'
print("\n2. IDENTIFICACION DE POSIBLES ANTICRESIS:")
print("   Basado en el análisis anterior, debería haber 7 registros 'anticresis'")
print("   que fueron cambiados a 'no_especificado'.")

# 3. Verificar si hay algún campo que indique el valor original
print("\n3. BUSCANDO CAMPOS QUE PUEDAN INDICAR EL VALOR ORIGINAL:")
print("   Campos disponibles en el modelo:")

# Listar todos los campos del modelo
fields = PropiedadRaw._meta.get_fields()
field_names = [field.name for field in fields if hasattr(field, 'name')]
print(f"   Total campos: {len(field_names)}")

# Buscar campos que puedan contener información sobre la condición
campos_relevantes = []
for field_name in field_names:
    if any(keyword in field_name.lower() for keyword in ['condicion', 'tipo', 'estado', 'original']):
        campos_relevantes.append(field_name)

print(f"   Campos potencialmente relevantes: {campos_relevantes}")

# 4. Verificar valores en campos relevantes para los registros con 'no_especificado'
print("\n4. VALORES EN CAMPOS RELEVANTES:")
if registros_no_esp.count() > 0:
    sample_reg = registros_no_esp.first()
    for campo in campos_relevantes:
        if hasattr(sample_reg, campo):
            valor = getattr(sample_reg, campo)
            print(f"   Campo '{campo}': {valor}")
        else:
            print(f"   Campo '{campo}': NO DISPONIBLE")

# 5. Recomendaciones
print("\n" + "="*60)
print("RECOMENDACIONES:")
print("")
print("1. REVISAR MANUALMENTE LOS 9 REGISTROS:")
print("   Los IDs son:")
if registros_no_esp.count() > 0:
    ids = [str(reg.id) for reg in registros_no_esp]
    print(f"   {', '.join(ids)}")
print("")
print("2. BUSCAR EN EL EXCEL ORIGINAL:")
print("   Abrir 'propiedadesraw_corregido (2).xlsx'")
print("   Buscar estos IDs o características similares")
print("   Verificar la columna 'condicion' original")
print("")
print("3. SI NO SE PUEDE IDENTIFICAR:")
print("   Opción A: Dejar como 'no_especificado' (9 registros)")
print("   Opción B: Asumir que 7 son 'anticresis' y 2 son 'no_especificado'")
print("")
print("4. PARA CORREGIR DEFINITIVAMENTE:")
print("   Ejecutar:")
print("   UPDATE ingestas_propiedadraw SET condicion='anticresis'")
print("   WHERE id IN (lista_de_ids_anticresis)")

print("\n" + "="*60)
print("¿QUÉ PREFIERES HACER?")
print("1. Dejar los 9 registros como 'no_especificado'")
print("2. Cambiar 7 registros a 'anticresis' (asumiendo)")
print("3. Revisar manualmente en el Excel")
print("4. Otra opción (especificar)")