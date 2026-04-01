#!/usr/bin/env python
"""
Verificar todos los campos del modelo PropiedadRaw para decidir cuáles incluir en list_display.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from ingestas.models import PropiedadRaw

print("=== CAMPOS DEL MODELO PROPIEDADRAW ===")
print("")

# Obtener todos los campos del modelo
fields = PropiedadRaw._meta.get_fields()

# Separar campos por tipo
campos_normales = []
campos_relacion = []
campos_many_to_many = []

for field in fields:
    if hasattr(field, 'name'):
        field_type = field.get_internal_type() if hasattr(field, 'get_internal_type') else type(field).__name__
        
        if field.many_to_many:
            campos_many_to_many.append((field.name, field_type))
        elif field.one_to_many or field.many_to_one:
            campos_relacion.append((field.name, field_type))
        else:
            campos_normales.append((field.name, field_type))

print(f"1. CAMPOS NORMALES ({len(campos_normales)}):")
print("   (Estos son los que normalmente se muestran en list_display)")
for i, (name, field_type) in enumerate(campos_normales, 1):
    print(f"   {i:2}. {name:30} ({field_type})")

print(f"\n2. CAMPOS DE RELACIÓN ({len(campos_relacion)}):")
for i, (name, field_type) in enumerate(campos_relacion, 1):
    print(f"   {i:2}. {name:30} ({field_type})")

print(f"\n3. CAMPOS MANY-TO-MANY ({len(campos_many_to_many)}):")
for i, (name, field_type) in enumerate(campos_many_to_many, 1):
    print(f"   {i:2}. {name:30} ({field_type})")

# Identificar campos importantes para list_display
print("\n" + "="*60)
print("CAMPOS IMPORTANTES PARA LIST_DISPLAY:")
print("")

campos_importantes = [
    'id',  # Siempre útil
    'identificador_externo',  # Mencionado por el usuario
    'id_propiedad',  # Similar a identificador_externo
    'tipo_propiedad',
    'condicion',
    'precio_usd',
    'departamento',
    'provincia',
    'distrito',
    'fuente_excel',
    'fecha_ingesta',
    'propiedad_verificada',
    'url_propiedad',  # Importante para enlaces
    'portal',  # De dónde viene
    'agente_inmobiliario',  # Información de contacto
]

print("Campos sugeridos para list_display:")
for i, campo in enumerate(campos_importantes, 1):
    # Verificar si el campo existe
    existe = any(campo == name for name, _ in campos_normales)
    status = "[OK]" if existe else "[NO EXISTE]"
    print(f"   {i:2}. {status} {campo}")

print("\n" + "="*60)
print("RECOMENDACIÓN PARA ACTUALIZAR ADMIN.PY:")
print("")
print("Sugiero actualizar list_display para incluir:")
print("")
print("list_display = (")
print("    'id', 'identificador_externo', 'tipo_propiedad', 'condicion',")
print("    'propiedad_verificada', 'precio_usd', 'departamento', 'provincia',")
print("    'distrito', 'fuente_excel', 'fecha_ingesta', 'url_propiedad',")
print("    'portal', 'agente_inmobiliario'")
print(")")
print("")
print("Esto mostraría 14 campos en lugar de los 12 actuales,")
print("incluyendo los campos importantes mencionados por el usuario.")