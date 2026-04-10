#!/usr/bin/env python3
"""
Debug para verificar la lógica de colores en la función.
"""

import os
import sys
import django

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from eventos.models import EventType

# Simular la lógica de la función
def debug_colores_logic():
    tipos_evento = EventType.objects.filter(is_active=True).order_by('name')
    
    colores_base = [
        '#3498db', '#2ecc71', '#e74c3c', '#f39c12', '#9b59b6', '#1abc9c',
        '#d35400', '#c0392b', '#16a085', '#8e44ad', '#27ae60', '#2980b9'
    ]
    
    color_index = 0
    colores_usados = set()
    colores_dict = {}
    
    print("=== DEBUG DE COLORES ===")
    print(f"Total tipos: {tipos_evento.count()}")
    
    for i, tipo in enumerate(tipos_evento):
        tipo_id = str(tipo.id)
        color_db = tipo.color if tipo.color else None
        
        print(f"\nTipo {i+1}: ID={tipo_id}, nombre='{tipo.name}', color_db='{color_db}'")
        print(f"  colores_usados: {colores_usados}")
        print(f"  color_index: {color_index}")
        
        if color_db and color_db not in colores_usados:
            colores_dict[tipo_id] = color_db
            colores_usados.add(color_db)
            print(f"  -> Usando color de BD (único): {color_db}")
        else:
            print(f"  -> Color de BD no disponible o duplicado, buscando en colores_base")
            # Buscar próximo color disponible
            while color_index < len(colores_base) and colores_base[color_index] in colores_usados:
                print(f"    Saltando color {colores_base[color_index]} (ya usado)")
                color_index += 1
            
            if color_index < len(colores_base):
                colores_dict[tipo_id] = colores_base[color_index]
                colores_usados.add(colores_base[color_index])
                print(f"  -> Asignando color de paleta: {colores_base[color_index]}")
                color_index += 1
            else:
                import random
                color_random = f'#{random.randint(0, 0xFFFFFF):06x}'
                colores_dict[tipo_id] = color_random
                colores_usados.add(color_random)
                print(f"  -> Generando color aleatorio: {color_random}")
    
    print("\n=== RESULTADO FINAL ===")
    for tipo_id, color in colores_dict.items():
        tipo = EventType.objects.get(id=int(tipo_id))
        print(f"  {tipo.name} (ID {tipo_id}): {color}")

if __name__ == '__main__':
    debug_colores_logic()