#!/usr/bin/env python
"""
Verificar la configuración del Django admin para PropiedadRaw.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.contrib import admin
from ingestas.models import PropiedadRaw

print("=== VERIFICACIÓN DE CONFIGURACIÓN DJANGO ADMIN ===")
print("")

# 1. Verificar si hay un ModelAdmin registrado para PropiedadRaw
try:
    # Obtener el sitio admin
    site = admin.site
    
    # Buscar el ModelAdmin para PropiedadRaw
    model_admin = None
    for model, admin_class in site._registry.items():
        if model == PropiedadRaw:
            model_admin = admin_class
            break
    
    if model_admin:
        print("1. MODELADMIN ENCONTRADO PARA PropiedadRaw")
        print(f"   Clase: {model_admin.__class__.__name__}")
        
        # Verificar list_display
        if hasattr(model_admin, 'list_display'):
            print(f"   list_display: {model_admin.list_display}")
            
            # Verificar si 'condicion' está en list_display
            if 'condicion' in model_admin.list_display:
                print("   ✓ 'condicion' está en list_display")
            else:
                print("   ✗ 'condicion' NO está en list_display")
        else:
            print("   ✗ No tiene list_display definido")
        
        # Verificar list_filter
        if hasattr(model_admin, 'list_filter'):
            print(f"   list_filter: {model_admin.list_filter}")
        else:
            print("   ✗ No tiene list_filter definido")
        
        # Verificar search_fields
        if hasattr(model_admin, 'search_fields'):
            print(f"   search_fields: {model_admin.search_fields}")
        else:
            print("   ✗ No tiene search_fields definido")
    else:
        print("1. ✗ NO HAY MODELADMIN REGISTRADO PARA PropiedadRaw")
        print("   El modelo no está registrado en admin.site")
        
except Exception as e:
    print(f"1. ERROR al verificar ModelAdmin: {e}")

print("\n2. VERIFICAR DEFINICIÓN DEL MODELO:")
print("   Campos del modelo PropiedadRaw:")

# Obtener todos los campos del modelo
fields = PropiedadRaw._meta.get_fields()
field_names = [field.name for field in fields if hasattr(field, 'name')]
print(f"   Total campos: {len(field_names)}")
print(f"   Campos: {field_names}")

# Verificar específicamente el campo 'condicion'
condicion_field = None
for field in fields:
    if hasattr(field, 'name') and field.name == 'condicion':
        condicion_field = field
        break

if condicion_field:
    print(f"\n   Campo 'condicion':")
    print(f"     Tipo: {condicion_field.get_internal_type()}")
    print(f"     Null permitido: {condicion_field.null}")
    print(f"     Blank permitido: {condicion_field.blank}")
    print(f"     Max length: {getattr(condicion_field, 'max_length', 'N/A')}")
    print(f"     Choices: {getattr(condicion_field, 'choices', 'N/A')}")
else:
    print("\n   ✗ Campo 'condicion' no encontrado en el modelo")

print("\n3. VERIFICAR DATOS DIRECTAMENTE DESDE LA BASE:")
print("   Consultando 5 registros aleatorios para ver sus valores reales:")

import random
from django.db.models import Q

# Obtener algunos IDs aleatorios
all_ids = list(PropiedadRaw.objects.values_list('id', flat=True))
if len(all_ids) > 5:
    sample_ids = random.sample(all_ids, 5)
else:
    sample_ids = all_ids

for i, id_val in enumerate(sample_ids, 1):
    try:
        obj = PropiedadRaw.objects.get(id=id_val)
        print(f"   {i}. ID: {obj.id}, Condición: '{obj.condicion}', Tipo: {obj.tipo_propiedad}")
        print(f"      Precio: {obj.precio_usd}, Depto: {obj.departamento}")
    except Exception as e:
        print(f"   {i}. Error al obtener ID {id_val}: {e}")

print("\n4. RECOMENDACIONES:")
print("   Si la base de datos muestra datos pero el admin no:")
print("   1. Verifica que el campo 'condicion' esté en list_display del ModelAdmin")
print("   2. Limpia la cache del navegador (Ctrl+F5)")
print("   3. Verifica si hay algún middleware que modifique los datos")
print("   4. Revisa el template admin/change_list.html personalizado si existe")
print("   5. Verifica los permisos del usuario en Django admin")

print("\n" + "="*60)
print("PASOS PARA CORREGIR:")
print("1. Abre el archivo admin.py de la app 'ingestas'")
print("2. Asegúrate de que 'condicion' esté en list_display")
print("3. Ejemplo:")
print("   class PropiedadRawAdmin(admin.ModelAdmin):")
print("       list_display = ['id', 'condicion', 'tipo_propiedad', 'precio_usd']")
print("4. Guarda y recarga la página del admin")