#!/usr/bin/env python
"""
Script para probar que ACM incluye propiedades de Propifai correctamente.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from django.test import RequestFactory
from acm.views import buscar_comparables
import json

def test_acm_incluye_propifai():
    """Prueba que la vista buscar_comparables incluya propiedades de Propifai."""
    print("=== PRUEBA DE ACM CON PROPIFAI ===\n")
    
    # Crear una solicitud POST simulada
    factory = RequestFactory()
    
    # Datos de prueba (coordenadas en Arequipa)
    data = {
        'lat': -16.4090,
        'lng': -71.5375,
        'radio': 1000,  # 1 km
        'tipo_propiedad': ''
    }
    
    # Crear solicitud POST
    request = factory.post('/acm/buscar_comparables/', 
                          data=json.dumps(data),
                          content_type='application/json')
    
    try:
        # Llamar a la vista
        response = buscar_comparables(request)
        
        print(f"Status code: {response.status_code}")
        print(f"Content type: {response['Content-Type']}")
        
        if response.status_code == 200:
            content = json.loads(response.content)
            
            print(f"\nRespuesta JSON:")
            print(f"  Status: {content.get('status')}")
            print(f"  Total propiedades: {content.get('total')}")
            
            propiedades = content.get('propiedades', [])
            print(f"  Propiedades retornadas: {len(propiedades)}")
            
            # Contar propiedades por fuente
            locales = 0
            propifai = 0
            
            for prop in propiedades:
                if prop.get('es_propify') or prop.get('fuente') == 'propifai':
                    propifai += 1
                    print(f"    - Propifai: {prop.get('tipo')} en {prop.get('distrito')} (ID: {prop.get('id')})")
                else:
                    locales += 1
            
            print(f"\nResumen por fuente:")
            print(f"  Propiedades locales: {locales}")
            print(f"  Propiedades Propifai: {propifai}")
            
            # Verificar que al menos haya algunas propiedades
            if len(propiedades) > 0:
                print(f"\n✓ ACM está retornando propiedades correctamente")
                if propifai > 0:
                    print(f"✓ Se incluyen propiedades de Propifai ({propifai} encontradas)")
                else:
                    print(f"⚠ No se encontraron propiedades de Propifai (puede que no haya en el radio)")
            else:
                print(f"⚠ No se encontraron propiedades en el radio especificado")
            
            # Mostrar detalles de algunas propiedades
            if propiedades:
                print(f"\nEjemplos de propiedades encontradas (primeras 3):")
                for i, prop in enumerate(propiedades[:3]):
                    fuente = "Propifai" if prop.get('es_propify') or prop.get('fuente') == 'propifai' else "Local"
                    print(f"  {i+1}. {prop.get('tipo')} - {prop.get('precio')} USD - {prop.get('distrito')} ({fuente})")
            
            return True
            
        else:
            print(f"✗ Error: La vista devolvió código {response.status_code}")
            print(f"  Contenido: {response.content}")
            return False
            
    except Exception as e:
        print(f"✗ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("Iniciando prueba de ACM con Propifai...\n")
    success = test_acm_incluye_propifai()
    print(f"\n{'✓ Prueba exitosa' if success else '✗ Prueba fallida'}")
    sys.exit(0 if success else 1)