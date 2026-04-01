#!/usr/bin/env python
"""
Script para probar las funciones de gráficos del dashboard de calidad de datos.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from market_analysis.charts import create_data_quality_summary, MATPLOTLIB_AVAILABLE

print("=== Prueba de gráficos de calidad de datos ===")
print(f"Matplotlib disponible: {MATPLOTLIB_AVAILABLE}")

try:
    charts = create_data_quality_summary()
    print(f"\nTotal de gráficos generados: {len(charts)}")
    
    for key, value in charts.items():
        if value:
            print(f"\n{key}:")
            print(f"  Tipo: {type(value)}")
            print(f"  Longitud: {len(value)}")
            print(f"  Empieza con: {value[:80]}...")
            
            # Verificar si contiene 'data:image'
            if 'data:image' in value:
                print(f"  ✓ Contiene 'data:image'")
                # Verificar tipo de imagen
                if 'data:image/png' in value:
                    print(f"  ✓ Es PNG base64")
                elif 'data:image/svg+xml' in value:
                    print(f"  ✓ Es SVG base64")
                else:
                    print(f"  ⚠ Tipo de imagen desconocido")
            else:
                print(f"  ✗ NO contiene 'data:image'")
        else:
            print(f"\n{key}: None o vacío")
            
except Exception as e:
    print(f"\nError al generar gráficos: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Fin de la prueba ===")