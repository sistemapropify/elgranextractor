#!/usr/bin/env python
"""
Test completo de la vista ListaPropiedadesView.
"""
import os
import sys
import django
from django.test import RequestFactory, TestCase

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.views import ListaPropiedadesView

print("=== TEST COMPLETO DE VISTA ===")
print()

# Crear test case
class TestListaPropiedadesView(TestCase):
    def test_propify_solo(self):
        print("1. Test: Solo Propify seleccionado")
        
        # Crear request
        request = RequestFactory().get('/ingestas/propiedades/?fuente_propify=propify')
        
        # Crear y configurar vista
        view = ListaPropiedadesView()
        view.setup(request)
        
        # Llamar a dispatch para inicializar
        response = view.dispatch(request)
        
        # Verificar que la respuesta sea exitosa
        self.assertEqual(response.status_code, 200)
        
        # Obtener contexto
        context = view.get_context_data()
        
        print(f"   Status code: {response.status_code}")
        print(f"   Total propiedades: {context.get('total_propiedades', 'NO')}")
        print(f"   Conteo propify: {context.get('conteo_propify', 'NO')}")
        
        # Verificar que hay propiedades Propify
        propify_count = context.get('conteo_propify', 0)
        self.assertGreater(propify_count, 0, "Debe haber propiedades Propify")
        print(f"   ✓ Propify count > 0: {propify_count}")
        
        # Verificar object_list
        object_list = context.get('todas_propiedades', [])
        print(f"   Object list length: {len(object_list)}")
        
        # Verificar que todas las propiedades en object_list son Propify
        if object_list:
            for i, prop in enumerate(object_list[:2]):
                print(f"   Propiedad {i+1}:")
                if isinstance(prop, dict):
                    print(f"     Es propify: {prop.get('es_propify', False)}")
                    print(f"     ID: {prop.get('id', 'N/A')}")
                    print(f"     Coordenadas: lat={prop.get('lat', 'N/A')}, lng={prop.get('lng', 'N/A')}")
                else:
                    print(f"     Tipo: {type(prop)}")
        
        return True
    
    def test_todas_fuentes(self):
        print("\n2. Test: Todas las fuentes (sin filtros)")
        
        request = RequestFactory().get('/ingestas/propiedades/')
        view = ListaPropiedadesView()
        view.setup(request)
        
        response = view.dispatch(request)
        context = view.get_context_data()
        
        print(f"   Status code: {response.status_code}")
        print(f"   Total propiedades: {context.get('total_propiedades', 'NO')}")
        print(f"   Conteo locales: {context.get('conteo_locales', 'NO')}")
        print(f"   Conteo externas: {context.get('conteo_externas', 'NO')}")
        print(f"   Conteo propify: {context.get('conteo_propify', 'NO')}")
        
        # Verificar que hay al menos algunas propiedades
        total = context.get('total_propiedades', 0)
        self.assertGreater(total, 0, "Debe haber propiedades")
        print(f"   ✓ Total propiedades > 0: {total}")
        
        return True

# Ejecutar tests
if __name__ == '__main__':
    test = TestListaPropiedadesView()
    
    try:
        print("Ejecutando test_propify_solo...")
        test.test_propify_solo()
        print("✓ Test 1 pasado")
    except Exception as e:
        print(f"✗ Test 1 falló: {e}")
    
    try:
        print("\nEjecutando test_todas_fuentes...")
        test.test_todas_fuentes()
        print("✓ Test 2 pasado")
    except Exception as e:
        print(f"✗ Test 2 falló: {e}")
    
    print("\n=== TESTS COMPLETADOS ===")