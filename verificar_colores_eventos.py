#!/usr/bin/env python3
"""
Verificar los colores de los tipos de eventos en la base de datos.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

from eventos.models import EventType

def verificar_colores():
    """Verificar los colores de los tipos de eventos."""
    print("=== Verificación de colores de tipos de eventos ===")
    
    tipos = EventType.objects.filter(is_active=True).order_by('name')
    
    print(f"Total de tipos activos: {tipos.count()}")
    print("\nDetalles de cada tipo:")
    
    colores_unicos = set()
    
    for tipo in tipos:
        color = tipo.color if tipo.color else 'No definido'
        colores_unicos.add(color)
        print(f"  - {tipo.name} (ID: {tipo.id}): {color}")
    
    print(f"\nColores únicos encontrados: {len(colores_unicos)}")
    for color in colores_unicos:
        print(f"  - {color}")
    
    # Verificar si hay colores duplicados o no definidos
    tipos_sin_color = [t for t in tipos if not t.color or t.color.strip() == '']
    if tipos_sin_color:
        print(f"\nTipos sin color definido: {len(tipos_sin_color)}")
        for tipo in tipos_sin_color:
            print(f"  - {tipo.name} (ID: {tipo.id})")
    
    return tipos

if __name__ == '__main__':
    verificar_colores()