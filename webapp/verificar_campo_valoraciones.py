#!/usr/bin/env python
"""
Verificar el tipo de campo 'valoraciones' en el modelo PropiedadRaw.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from ingestas.models import PropiedadRaw

print("=== VERIFICACION DEL CAMPO 'valoraciones' ===")
print("")

# Buscar el campo 'valoraciones'
field = None
for f in PropiedadRaw._meta.get_fields():
    if hasattr(f, 'name') and f.name == 'valoraciones':
        field = f
        break

if field:
    print(f"1. CAMPO ENCONTRADO: {field.name}")
    print(f"   Tipo interno: {field.get_internal_type() if hasattr(field, 'get_internal_type') else 'N/A'}")
    print(f"   Clase: {field.__class__.__name__}")
    print(f"   Many-to-many: {field.many_to_many}")
    print(f"   Many-to-one: {field.many_to_one}")
    print(f"   One-to-many: {field.one_to_many}")
    print(f"   One-to-one: {field.one_to_one}")
    
    # Verificar si es una relación
    if hasattr(field, 'related_model'):
        print(f"   Modelo relacionado: {field.related_model}")
    
    # Verificar si es un campo ManyToManyField
    from django.db.models import ManyToManyField
    if isinstance(field, ManyToManyField):
        print("   [CONFIRMADO] Es un campo ManyToManyField")
        print("   [PROBLEMA] Django admin no permite ManyToManyField en list_display")
        
elif 'valoraciones' in [f.name for f in PropiedadRaw._meta.get_fields() if hasattr(f, 'name')]:
    print("1. Campo 'valoraciones' existe pero no se pudo obtener información detallada")
else:
    print("1. [ERROR] Campo 'valoraciones' no encontrado en el modelo")

# Verificar todos los campos del modelo para identificar problemas similares
print("\n2. VERIFICANDO TODOS LOS CAMPOS PARA PROBLEMAS SIMILARES:")
fields = PropiedadRaw._meta.get_fields()
problemas = []

for f in fields:
    if hasattr(f, 'name'):
        if f.many_to_many or f.one_to_many:
            problemas.append((f.name, 'ManyToMany' if f.many_to_many else 'ReverseForeignKey'))
            print(f"   [PROBLEMA] {f.name}: {problemas[-1][1]}")

if problemas:
    print(f"\n   Total campos problemáticos: {len(problemas)}")
    print("   Estos campos NO pueden estar en list_display de Django admin")
else:
    print("\n   [OK] No hay campos problemáticos")

print("\n3. SOLUCION:")
print("   Opción 1: Quitar 'valoraciones' de list_display")
print("   Opción 2: Crear un método personalizado en PropiedadRawAdmin")
print("   Opción 3: Mostrar solo una representación del campo (ej: contar relaciones)")

print("\n4. RECOMENDACION:")
print("   Quitar 'valoraciones' de list_display ya que es un campo ManyToMany")
print("   y Django admin no lo soporta directamente en list_display")
print("   Se pueden mostrar los otros 38 campos sin problemas")