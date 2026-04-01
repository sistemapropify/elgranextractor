#!/usr/bin/env python
"""
Script para probar la función get_problematic_examples después de las correcciones
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from market_analysis.charts import get_problematic_examples

print("=== Probando get_problematic_examples para base local ===")
try:
    examples_local = get_problematic_examples('local', limit=2)
    print(f"Total tipos de problemas: {len(examples_local)}")
    
    for problem_type, items in examples_local.items():
        print(f"\n{problem_type}: {len(items)} items")
        if items:
            for i, item in enumerate(items[:2]):  # Mostrar máximo 2
                print(f"  {i+1}. ID: {item.get('id')}")
                if 'descripcion' in item:
                    desc = item.get('descripcion', 'Sin descripción')
                    print(f"     Descripción: {desc[:50] if desc else 'N/A'}...")
                elif 'title' in item:
                    print(f"     Título: {item.get('title', 'Sin título')[:50]}...")
                print(f"     Precio: {item.get('precio_usd', item.get('price', 'N/A'))}")
                print(f"     Área: {item.get('area_construida', item.get('built_area', 'N/A'))}")
                if 'coordenadas' in item:
                    print(f"     Coordenadas: '{item.get('coordenadas', 'N/A')}'")
                elif 'coordinates' in item:
                    print(f"     Coordinates: '{item.get('coordinates', 'N/A')}'")
except Exception as e:
    print(f"Error en base local: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Probando get_problematic_examples para Propifai ===")
try:
    examples_propifai = get_problematic_examples('propifai', limit=2)
    print(f"Total tipos de problemas: {len(examples_propifai)}")
    
    for problem_type, items in examples_propifai.items():
        print(f"\n{problem_type}: {len(items)} items")
        if items:
            for i, item in enumerate(items[:2]):  # Mostrar máximo 2
                print(f"  {i+1}. ID: {item.get('id')}")
                if 'title' in item:
                    print(f"     Título: {item.get('title', 'Sin título')[:50]}...")
                print(f"     Precio: {item.get('price', 'N/A')}")
                print(f"     Área: {item.get('built_area', 'N/A')}")
                if 'coordinates' in item:
                    print(f"     Coordinates: '{item.get('coordinates', 'N/A')}'")
except Exception as e:
    print(f"Error en Propifai: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Verificando conteo total de problemas ===")
try:
    from market_analysis.views import data_quality_dashboard
    from django.test import RequestFactory
    
    # Crear una request simulada
    factory = RequestFactory()
    request = factory.get('/market-analysis/data-quality/')
    
    # Importar la vista y llamarla
    print("Nota: Para probar la vista completa necesitaríamos un servidor Django corriendo")
    print("Pero podemos verificar que las funciones individuales funcionen")
    
except Exception as e:
    print(f"Error al probar vista: {e}")