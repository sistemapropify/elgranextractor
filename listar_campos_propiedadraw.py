#!/usr/bin/env python
"""
Script para listar todos los campos del modelo PropiedadRaw.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw

def listar_campos():
    print("=== CAMPOS DEL MODELO PropiedadRaw ===")
    print(f"Total de campos: {len(PropiedadRaw._meta.get_fields())}")
    print()
    
    # Separar por tipo de campo
    campos_relacion = []
    campos_normales = []
    
    for field in PropiedadRaw._meta.get_fields():
        if field.is_relation:
            campos_relacion.append(field)
        else:
            campos_normales.append(field)
    
    print("--- CAMPOS NORMALES (no relaciones) ---")
    for field in campos_normales:
        print(f"• {field.name}")
        print(f"  Tipo: {field.__class__.__name__}")
        
        # Información específica según tipo
        if hasattr(field, 'max_length'):
            print(f"  max_length: {field.max_length}")
        if hasattr(field, 'null'):
            print(f"  null: {field.null}")
        if hasattr(field, 'blank'):
            print(f"  blank: {field.blank}")
        if hasattr(field, 'verbose_name'):
            print(f"  verbose_name: {field.verbose_name}")
        if hasattr(field, 'help_text') and field.help_text:
            print(f"  help_text: {field.help_text}")
        if hasattr(field, 'choices') and field.choices:
            print(f"  choices: {[c[0] for c in field.choices]}")
        if hasattr(field, 'db_column') and field.db_column != field.name:
            print(f"  db_column: {field.db_column}")
        if hasattr(field, 'default') and field.default is not None:
            print(f"  default: {field.default}")
        print()
    
    print("--- CAMPOS DE RELACIÓN ---")
    for field in campos_relacion:
        print(f"• {field.name}")
        print(f"  Tipo: {field.__class__.__name__}")
        print(f"  Modelo relacionado: {field.related_model.__name__}")
        print(f"  Relación inversa: {field.related_query_name()}")
        print()
    
    # Lista simple para copiar y pegar
    print("=== LISTA SIMPLE DE NOMBRES DE CAMPOS ===")
    nombres = [field.name for field in campos_normales]
    print(", ".join(sorted(nombres)))
    
    print("\n=== CAMPOS CON VALORES POR DEFECTO ===")
    for field in campos_normales:
        if hasattr(field, 'default') and field.default is not None:
            print(f"{field.name}: {field.default}")

if __name__ == '__main__':
    try:
        listar_campos()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)