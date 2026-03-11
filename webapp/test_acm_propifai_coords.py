#!/usr/bin/env python
"""
Script para probar si las propiedades de Propifai ahora tienen coordenadas en ACM.
"""
import os
import sys

# Cambiar al directorio actual (webapp)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Agregar directorio padre al path para importar webapp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    import django
    django.setup()
    print("OK - Django configurado correctamente")
except Exception as e:
    print(f"ERROR - Configurando Django: {e}")
    sys.exit(1)

def test_propifai_coordenadas():
    """Probar si las propiedades de Propifai tienen coordenadas."""
    print("=== PRUEBA COORDENADAS PROPIFAI ===")
    
    try:
        from propifai.models import PropifaiProperty
        
        # Obtener algunas propiedades
        props = PropifaiProperty.objects.using('propifai').all()[:10]
        print(f"OK - Obtenidas {len(list(props))} propiedades de Propifai")
        
        # Reiniciar el queryset
        props = PropifaiProperty.objects.using('propifai').all()[:10]
        
        for i, prop in enumerate(props):
            print(f"\nPropiedad {i}: ID={prop.id}, tipo={prop.property_type}")
            print(f"  Campo coordinates: '{prop.coordinates}'")
            print(f"  Propiedad latitude: {prop.latitude}")
            print(f"  Propiedad longitude: {prop.longitude}")
            print(f"  Distrito: {prop.district}")
            
            # Verificar formato de coordinates
            if prop.coordinates:
                print(f"  Formato coordinates: {type(prop.coordinates)}")
                # Intentar parsear
                try:
                    parts = prop.coordinates.split(',')
                    print(f"  Partes separadas por coma: {parts}")
                    if len(parts) >= 2:
                        lat = float(parts[0].strip())
                        lng = float(parts[1].strip())
                        print(f"  Parseado manual: lat={lat}, lng={lng}")
                except Exception as e:
                    print(f"  Error parseando coordinates: {e}")
            else:
                print("  coordinates está vacío o es None")
                
    except Exception as e:
        print(f"ERROR - Probando coordenadas: {e}")
        import traceback
        traceback.print_exc()

def test_acm_view_direct():
    """Probar la vista ACM directamente."""
    print("\n=== PRUEBA VISTA ACM DIRECTA ===")
    
    try:
        from django.test import RequestFactory
        import json
        from acm.views import buscar_comparables
        
        factory = RequestFactory()
        data = {
            'lat': -16.4090,
            'lng': -71.5375,
            'radio': 5000,  # 5 km
            'tipo_propiedad': ''
        }
        
        request = factory.post('/acm/buscar-comparables/', 
                              data=json.dumps(data),
                              content_type='application/json')
        
        response = buscar_comparables(request)
        
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            result = json.loads(response.content)
            print(f"Total propiedades: {result.get('total')}")
            
            if result.get('propiedades'):
                locales = 0
                propifai = 0
                
                for i, p in enumerate(result['propiedades'][:5]):
                    fuente = p.get('fuente', 'desconocida')
                    es_propify = p.get('es_propify', False)
                    
                    if fuente == 'propifai' or es_propify:
                        propifai += 1
                        print(f"  PROPIFAI {i}: tipo={p.get('tipo')}, distrito={p.get('distrito')}, lat={p.get('lat')}, lng={p.get('lng')}")
                    else:
                        locales += 1
                        print(f"  LOCAL {i}: tipo={p.get('tipo')}, distrito={p.get('distrito')}, lat={p.get('lat')}, lng={p.get('lng')}")
                
                print(f"\nResumen: {locales} locales, {propifai} Propifai")
                
                if propifai > 0:
                    print("SUCCESS - ¡Se encontraron propiedades de Propifai en ACM!")
                else:
                    print("WARNING - No se encontraron propiedades de Propifai")
            else:
                print("WARNING - No se encontraron propiedades en absoluto")
        else:
            print(f"ERROR - Respuesta: {response.content}")
            
    except Exception as e:
        print(f"ERROR - Probando vista ACM: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_propifai_coordenadas()
    test_acm_view_direct()