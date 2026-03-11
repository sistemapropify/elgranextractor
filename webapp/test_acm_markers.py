#!/usr/bin/env python
"""
Script para probar que los marcadores de ACM muestren correctamente la fuente de las propiedades.
"""
import os
import sys
import django
import json

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import Client

def test_acm_buscar_comparables():
    """Probar el endpoint buscar-comparables para verificar que incluye es_propify."""
    client = Client()
    
    # Datos de prueba
    data = {
        'lat': -16.4090,  # Arequipa
        'lng': -71.5375,
        'radio': 1000,  # 1 km
        'tipo_propiedad': 'Casa'
    }
    
    print("=== PRUEBA ACM BUSCAR COMPARABLES ===")
    print(f"Datos: {data}")
    
    try:
        response = client.post('/acm/buscar-comparables/', 
                              json.dumps(data), 
                              content_type='application/json')
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = json.loads(response.content)
            print(f"Total propiedades: {result.get('total')}")
            
            if result.get('propiedades'):
                prop_locales = 0
                prop_propifai = 0
                
                for i, p in enumerate(result['propiedades'][:5]):  # Mostrar primeras 5
                    fuente = p.get('fuente', 'desconocida')
                    es_propify = p.get('es_propify', False)
                    tipo = p.get('tipo', 'N/A')
                    distrito = p.get('distrito', 'N/A')
                    
                    print(f"  Propiedad {i}:")
                    print(f"    Tipo: {tipo}")
                    print(f"    Fuente: {fuente}")
                    print(f"    es_propify: {es_propify}")
                    print(f"    Distrito: {distrito}")
                    print(f"    Distancia: {p.get('distancia_metros', 'N/A')} m")
                    
                    if fuente == 'propifai' or es_propify:
                        prop_propifai += 1
                    else:
                        prop_locales += 1
                
                print(f"\nResumen: {prop_locales} locales, {prop_propifai} Propifai")
                
                # Verificar que las propiedades Propifai tienen es_propify=True
                for p in result['propiedades']:
                    if p.get('fuente') == 'propifai' and not p.get('es_propify'):
                        print("ERROR: Propiedad con fuente='propifai' pero es_propify=False")
                    if p.get('fuente') == 'local' and p.get('es_propify'):
                        print("ERROR: Propiedad con fuente='local' pero es_propify=True")
            
            else:
                print("No se encontraron propiedades")
        else:
            print(f"Error: {response.content}")
            
    except Exception as e:
        print(f"Excepción: {e}")
        import traceback
        traceback.print_exc()

def test_acm_view():
    """Probar la vista principal de ACM."""
    client = Client()
    
    print("\n=== PRUEBA VISTA PRINCIPAL ACM ===")
    
    try:
        response = client.get('/acm/')
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            # Verificar que el template se renderiza correctamente
            content = response.content.decode('utf-8')
            
            # Buscar elementos clave
            if 'acmMap' in content:
                print("✓ Mapa ACM encontrado en el template")
            else:
                print("✗ Mapa ACM NO encontrado en el template")
                
            if 'buscarComparables' in content:
                print("✓ Función buscarComparables encontrada")
            else:
                print("✗ Función buscarComparables NO encontrada")
                
            # Verificar que hay tipos de propiedad
            if 'tipos_propiedad' in content:
                print("✓ Tipos de propiedad incluidos")
            else:
                print("✗ Tipos de propiedad NO incluidos")
        else:
            print(f"Error: {response.content}")
            
    except Exception as e:
        print(f"Excepción: {e}")

if __name__ == '__main__':
    test_acm_view()
    test_acm_buscar_comparables()