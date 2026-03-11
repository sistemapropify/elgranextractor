#!/usr/bin/env python
"""
Script simple para listar todos los campos del modelo PropiedadRaw.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw

def listar_campos_simple():
    print("=== CAMPOS DEL MODELO PropiedadRaw ===")
    print(f"Total de campos: {len(PropiedadRaw._meta.get_fields())}")
    print()
    
    # Lista ordenada alfabéticamente
    campos_normales = []
    for field in PropiedadRaw._meta.get_fields():
        if not field.is_relation:
            campos_normales.append(field)
    
    # Ordenar por nombre
    campos_normales.sort(key=lambda x: x.name)
    
    print("--- LISTA DE CAMPOS ---")
    for i, field in enumerate(campos_normales, 1):
        tipo = field.__class__.__name__
        null_blank = ""
        if field.null and field.blank:
            null_blank = "(nullable)"
        elif field.null:
            null_blank = "(null)"
        elif field.blank:
            null_blank = "(blank)"
        
        # Información adicional
        extra = []
        if hasattr(field, 'max_length') and field.max_length:
            extra.append(f"max_length={field.max_length}")
        if hasattr(field, 'choices') and field.choices:
            extra.append(f"choices={len(field.choices)}")
        if hasattr(field, 'verbose_name') and field.verbose_name != field.name:
            extra.append(f"verbose='{field.verbose_name}'")
        
        extra_str = ", ".join(extra)
        if extra_str:
            extra_str = f" - {extra_str}"
        
        print(f"{i:2d}. {field.name:25} {tipo:20} {null_blank:12}{extra_str}")
    
    print()
    print("--- NOMBRES PARA COPIAR ---")
    nombres = [field.name for field in campos_normales]
    print(", ".join(nombres))
    
    print()
    print("--- CAMPOS NUEVOS/ESPECIALES ---")
    nuevos = ['identificador_externo', 'estado_propiedad', 'fecha_venta', 'precio_final_venta', 'atributos_extras']
    for campo in nuevos:
        if campo in nombres:
            field = PropiedadRaw._meta.get_field(campo)
            print(f"• {campo}: {field.__class__.__name__}")
            if hasattr(field, 'help_text') and field.help_text:
                print(f"  {field.help_text}")

if __name__ == '__main__':
    try:
        listar_campos_simple()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)