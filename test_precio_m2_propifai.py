#!/usr/bin/env python
"""
Script para probar que el precio por metro cuadrado se calcula correctamente
para propiedades de Propifai en la vista ACM.
"""
import os
import sys
import django
import json

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from acm.views import buscar_comparables
from propifai.models import PropifaiProperty

def test_precio_m2_propifai():
    """Prueba que propiedades de Propifai tengan precio_m2 y precio_m2_final."""
    print("=== Prueba de cálculo de precio por m² para Propifai ===")
    
    # Obtener algunas propiedades de Propifai con datos de prueba
    propiedades = PropifaiProperty.objects.filter(
        price__isnull=False,
        built_area__isnull=False
    )[:5]
    
    if not propiedades.exists():
        print("No se encontraron propiedades de Propifai con price y built_area.")
        # Buscar propiedades con land_area como alternativa
        propiedades = PropifaiProperty.objects.filter(
            price__isnull=False,
            land_area__isnull=False
        )[:5]
        print(f"Encontradas {propiedades.count()} propiedades con land_area.")
    
    for prop in propiedades:
        print(f"\nPropiedad ID: {prop.id}, Código: {prop.code}")
        print(f"  Precio: {prop.price}, Built Area: {prop.built_area}, Land Area: {prop.land_area}")
        
        # Simular cálculo manual
        area_para_calculo = None
        if prop.built_area and float(prop.built_area) > 0:
            area_para_calculo = float(prop.built_area)
        elif prop.land_area and float(prop.land_area) > 0:
            area_para_calculo = float(prop.land_area)
        
        if prop.price and area_para_calculo:
            precio_m2 = float(prop.price) / area_para_calculo
            print(f"  Precio/m² calculado: {precio_m2:.2f}")
        else:
            print("  No se puede calcular precio/m² (falta precio o área)")
    
    # Probar la vista directamente con una solicitud simulada
    print("\n=== Probando vista buscar_comparables ===")
    factory = RequestFactory()
    data = {
        'lat': -12.0464,  # Lima centro
        'lng': -77.0428,
        'radio': 1000,  # 1 km
        'tipo_propiedad': 'Casa',
        'precio_min': 0,
        'precio_max': 1000000,
        'metros_min': 0,
        'metros_max': 1000,
    }
    
    request = factory.post('/acm/buscar-comparables/', 
                          data=json.dumps(data),
                          content_type='application/json')
    
    try:
        response = buscar_comparables(request)
        if response.status_code == 200:
            result = json.loads(response.content)
            print(f"Total propiedades encontradas: {result['total']}")
            
            propifai_count = 0
            for prop in result['propiedades']:
                if prop['fuente'] == 'propifai':
                    propifai_count += 1
                    print(f"\nPropiedad Propifai ID: {prop['id']}")
                    print(f"  Precio/m²: {prop['precio_m2']}")
                    print(f"  Precio/m² final: {prop['precio_m2_final']}")
                    print(f"  Tiene precio_m2: {prop['precio_m2'] is not None}")
            
            print(f"\nTotal propiedades Propifai en respuesta: {propifai_count}")
        else:
            print(f"Error en respuesta: {response.status_code}")
            print(response.content)
    except Exception as e:
        print(f"Error al ejecutar vista: {e}")

if __name__ == '__main__':
    test_precio_m2_propifai()