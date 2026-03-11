#!/usr/bin/env python
"""
Test final para verificar la vista completa.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory, TestCase
from ingestas.views import ListaPropiedadesView

print("=== TEST VISTA FINAL ===")
print()

class TestListaPropiedadesView(TestCase):
    def test_filtrar_solo_propify(self):
        print("Test: Filtrar solo Propify")
        factory = RequestFactory()
        request = factory.get('/ingestas/propiedades/?fuente_propify=propify')
        
        view = ListaPropiedadesView()
        view.setup(request)
        
        # Llamar a get() que es lo que hace Django
        response = view.get(request)
        
        # Verificar respuesta
        self.assertEqual(response.status_code, 200)
        print(f"   Status code: {response.status_code} (OK)")
        
        # Verificar contexto
        context = response.context_data
        print(f"   Conteo locales: {context.get('conteo_locales', 0)}")
        print(f"   Conteo externas: {context.get('conteo_externas', 0)}")
        print(f"   Conteo propify: {context.get('conteo_propify', 0)}")
        print(f"   Total propiedades: {context.get('total_propiedades', 0)}")
        
        # Verificar que conteo_propify no sea 0
        conteo_propify = context.get('conteo_propify', 0)
        self.assertGreater(conteo_propify, 0, "El conteo de Propify debería ser mayor que 0")
        print(f"   Conteo Propify > 0: SI ({conteo_propify})")
        
        # Verificar que todas_propiedades contiene propiedades
        todas_propiedades = context.get('todas_propiedades', [])
        print(f"   Propiedades en página: {len(todas_propiedades)}")
        
        # Verificar que hay propiedades Propify
        if todas_propiedades:
            # Verificar el tipo del primer elemento
            primer_elem = todas_propiedades[0]
            print(f"   Tipo primer elemento: {type(primer_elem)}")
            
            # Si es diccionario, verificar es_propify
            if isinstance(primer_elem, dict):
                tiene_es_propify = primer_elem.get('es_propify', False)
                print(f"   Tiene es_propify: {tiene_es_propify}")
                
                # Contar propiedades Propify
                propify_count = sum(1 for p in todas_propiedades if p.get('es_propify'))
                print(f"   Propiedades Propify en página: {propify_count}")
            else:
                print(f"   ERROR: El elemento no es un diccionario")
        
        print("   Test PASSED")
        return True
    
    def test_filtrar_todas_fuentes(self):
        print("\nTest: Mostrar todas las fuentes (por defecto)")
        factory = RequestFactory()
        request = factory.get('/ingestas/propiedades/')
        
        view = ListaPropiedadesView()
        view.setup(request)
        response = view.get(request)
        
        context = response.context_data
        print(f"   Conteo locales: {context.get('conteo_locales', 0)}")
        print(f"   Conteo externas: {context.get('conteo_externas', 0)}")
        print(f"   Conteo propify: {context.get('conteo_propify', 0)}")
        
        # Verificar que todas las fuentes están activas por defecto
        self.assertTrue(context.get('fuente_local_checked', False), "fuente_local debería estar activa por defecto")
        self.assertTrue(context.get('fuente_externa_checked', False), "fuente_externa debería estar activa por defecto")
        self.assertTrue(context.get('fuente_propify_checked', False), "fuente_propify debería estar activa por defecto")
        print(f"   Todas las fuentes activas por defecto: SI")
        
        print("   Test PASSED")
        return True

# Ejecutar tests
test = TestListaPropiedadesView()
print("Ejecutando tests...")
print("-" * 50)

try:
    test.test_filtrar_solo_propify()
except Exception as e:
    print(f"   Test FAILED: {e}")
    import traceback
    traceback.print_exc()

try:
    test.test_filtrar_todas_fuentes()
except Exception as e:
    print(f"   Test FAILED: {e}")
    import traceback
    traceback.print_exc()

print()
print("=== FIN TEST VISTA ===")