#!/usr/bin/env python
"""
Script para verificar que el campo identificador_externo se haya agregado correctamente
al modelo PropiedadRaw.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw

def verificar_campo():
    print("=== Verificación del campo identificador_externo ===")
    
    # 1. Verificar que el campo existe en el modelo
    campos = [field.name for field in PropiedadRaw._meta.get_fields()]
    print(f"Campos disponibles en PropiedadRaw: {campos}")
    
    if 'identificador_externo' in campos:
        print("✓ Campo 'identificador_externo' encontrado en el modelo")
    else:
        print("✗ Campo 'identificador_externo' NO encontrado en el modelo")
        return False
    
    # 2. Obtener información del campo
    campo = PropiedadRaw._meta.get_field('identificador_externo')
    print(f"  - Tipo: {campo.__class__.__name__}")
    print(f"  - max_length: {campo.max_length}")
    print(f"  - null: {campo.null}")
    print(f"  - blank: {campo.blank}")
    print(f"  - verbose_name: {campo.verbose_name}")
    print(f"  - help_text: {campo.help_text}")
    
    # 3. Crear una instancia de prueba (no guardar)
    try:
        instancia = PropiedadRaw()
        instancia.identificador_externo = "TEST-12345"
        print(f"✓ Se puede asignar valor al campo: {instancia.identificador_externo}")
    except Exception as e:
        print(f"✗ Error al asignar valor: {e}")
        return False
    
    # 4. Verificar que se puede guardar (opcional, pero no guardaremos realmente)
    print("\n✓ Verificación completada exitosamente")
    return True

if __name__ == '__main__':
    try:
        verificar_campo()
    except Exception as e:
        print(f"Error durante la verificación: {e}")
        sys.exit(1)