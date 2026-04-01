#!/usr/bin/env python
"""
Verificar que TODOS los campos del modelo PropiedadRaw están en list_display del admin.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from ingestas.models import PropiedadRaw
from django.contrib import admin

print("=== VERIFICACION DE CAMPOS EN ADMIN ===")
print("")

# 1. Obtener todos los campos del modelo
fields = PropiedadRaw._meta.get_fields()
campos_modelo = []
for field in fields:
    if hasattr(field, 'name'):
        campos_modelo.append(field.name)

print(f"1. TOTAL CAMPOS EN EL MODELO: {len(campos_modelo)}")
print(f"   Campos: {campos_modelo}")

# 2. Obtener list_display actual del admin
print("\n2. LIST_DISPLAY EN ADMIN.PY:")
site = admin.site
model_admin = None
for model, admin_class in site._registry.items():
    if model == PropiedadRaw:
        model_admin = admin_class
        break

if model_admin:
    if hasattr(model_admin, 'list_display'):
        list_display_actual = model_admin.list_display
        print(f"   Total campos en list_display: {len(list_display_actual)}")
        print(f"   Campos: {list_display_actual}")
    else:
        print("   [ERROR] No tiene list_display definido")
        list_display_actual = []
else:
    print("   [ERROR] No hay ModelAdmin registrado para PropiedadRaw")
    list_display_actual = []

# 3. Comparar campos del modelo vs list_display
print("\n3. COMPARACION:")
campos_faltantes = []
for campo in campos_modelo:
    if campo not in list_display_actual:
        campos_faltantes.append(campo)

if campos_faltantes:
    print(f"   [ERROR] Faltan {len(campos_faltantes)} campos en list_display:")
    for i, campo in enumerate(campos_faltantes, 1):
        print(f"   {i:2}. {campo}")
else:
    print("   [OK] Todos los campos del modelo están en list_display")

# 4. Verificar campos adicionales en list_display
print("\n4. CAMPOS ADICIONALES EN LIST_DISPLAY:")
campos_extra = []
for campo in list_display_actual:
    if campo not in campos_modelo:
        campos_extra.append(campo)

if campos_extra:
    print(f"   [ADVERTENCIA] Hay {len(campos_extra)} campos en list_display que no están en el modelo:")
    for i, campo in enumerate(campos_extra, 1):
        print(f"   {i:2}. {campo}")
else:
    print("   [OK] No hay campos extra en list_display")

# 5. Verificar campos específicos mencionados por el usuario
print("\n5. CAMPOS ESPECIFICOS MENCIONADOS:")
campos_especificos = ['identificador_externo', 'id_propiedad', 'url_propiedad', 'condicion']
for campo in campos_especificos:
    if campo in list_display_actual:
        print(f"   [OK] '{campo}' está en list_display")
    else:
        print(f"   [ERROR] '{campo}' NO está en list_display")

# 6. Resumen
print("\n" + "="*60)
print("RESUMEN:")
print(f"   - Campos en el modelo: {len(campos_modelo)}")
print(f"   - Campos en list_display: {len(list_display_actual)}")
print(f"   - Campos faltantes: {len(campos_faltantes)}")
print(f"   - Campos extra: {len(campos_extra)}")

if len(campos_faltantes) == 0:
    print("\n   [OK] TODOS LOS CAMPOS ESTÁN INCLUIDOS EN EL ADMIN")
    print("   El Django admin ahora mostrará absolutamente todos los campos.")
else:
    print(f"\n   [ERROR] Faltan {len(campos_faltantes)} campos por incluir")

print("\n" + "="*60)
print("INSTRUCCIONES:")
print("1. Recarga la página del Django admin (Ctrl+F5)")
print("2. Verifica que ahora se muestren TODOS los campos")
print("3. Si algún campo importante aún no aparece, verifica:")
print("   - Que el campo exista en el modelo")
print("   - Que esté correctamente escrito en list_display")
print("   - Que no haya errores de sintaxis en admin.py")