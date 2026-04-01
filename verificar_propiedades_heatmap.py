#!/usr/bin/env python
"""
Script para verificar cuántas propiedades hay en la base de datos
y comparar con lo que muestra el heatmap.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from ingestas.models import PropiedadRaw
from propifai.models import PropifaiProperty

def main():
    print("=== VERIFICACIÓN DE PROPIEDADES PARA HEATMAP ===\n")
    
    # Contar propiedades con coordenadas válidas
    try:
        local_with_coords = PropiedadRaw.objects.filter(
            coordenadas__isnull=False
        ).exclude(coordenadas='').count()
        
        print(f"1. Propiedades locales (Remax) con coordenadas válidas: {local_with_coords}")
    except Exception as e:
        print(f"Error contando propiedades locales: {e}")
        local_with_coords = 0
    
    # Contar propiedades Propifai con coordenadas
    try:
        propifai_with_coords = PropifaiProperty.objects.filter(
            coordinates__isnull=False
        ).exclude(coordinates='').count()
        
        print(f"2. Propiedades Propifai con coordenadas válidas: {propifai_with_coords}")
    except Exception as e:
        print(f"Error contando propiedades Propifai: {e}")
        propifai_with_coords = 0
    
    total_with_coords = local_with_coords + propifai_with_coords
    print(f"\n3. TOTAL propiedades con coordenadas válidas: {total_with_coords}")
    
    # Contar todas las propiedades (sin filtro de coordenadas)
    try:
        total_local_all = PropiedadRaw.objects.count()
        print(f"\n4. Total propiedades locales (todas): {total_local_all}")
    except Exception as e:
        print(f"Error contando total local: {e}")
        total_local_all = 0
    
    try:
        total_propifai_all = PropifaiProperty.objects.count()
        print(f"5. Total propiedades Propifai (todas): {total_propifai_all}")
    except Exception as e:
        print(f"Error contando total Propifai: {e}")
        total_propifai_all = 0
    
    total_all = total_local_all + total_propifai_all
    print(f"6. TOTAL general de propiedades: {total_all}")
    
    # Calcular porcentaje de propiedades con coordenadas
    if total_all > 0:
        pct_with_coords = (total_with_coords / total_all) * 100
        print(f"\n7. Porcentaje de propiedades con coordenadas: {pct_with_coords:.1f}%")
    
    # Verificar si hay propiedades sin coordenadas
    if total_local_all > 0:
        local_no_coords = total_local_all - local_with_coords
        print(f"\n8. Propiedades locales SIN coordenadas: {local_no_coords}")
    
    if total_propifai_all > 0:
        propifai_no_coords = total_propifai_all - propifai_with_coords
        print(f"9. Propiedades Propifai SIN coordenadas: {propifai_no_coords}")
    
    print("\n=== RESUMEN ===")
    print(f"El heatmap debería mostrar aproximadamente {total_with_coords} propiedades")
    print(f"(basado en propiedades con coordenadas válidas)")
    print(f"\nSi el heatmap muestra 1541 propiedades (como en los logs),")
    print(f"entonces está mostrando {local_with_coords} de {total_local_all} propiedades locales.")
    
    # Comparación específica
    if local_with_coords > 0:
        print(f"\nEl heatmap está mostrando {1541} propiedades locales.")
        print(f"Esto representa el {(1541/local_with_coords)*100:.1f}% de las {local_with_coords} propiedades locales con coordenadas.")

if __name__ == "__main__":
    main()