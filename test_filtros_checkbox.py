#!/usr/bin/env python
"""
Script para probar la lógica de checkboxes en ListaPropiedadesView.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from ingestas.views import ListaPropiedadesView

def test_checkbox_logic():
    """Prueba la lógica de checkboxes con diferentes parámetros GET."""
    
    factory = RequestFactory()
    
    test_cases = [
        {
            'name': 'Sin parámetros - debería mostrar todos',
            'params': {},
            'expected': (True, True, True)
        },
        {
            'name': 'Solo fuente_local marcado',
            'params': {'fuente_local': 'local'},
            'expected': (True, False, False)
        },
        {
            'name': 'Solo fuente_externa marcado',
            'params': {'fuente_externa': 'externa'},
            'expected': (False, True, False)
        },
        {
            'name': 'Solo fuente_propify marcado',
            'params': {'fuente_propify': 'propify'},
            'expected': (False, False, True)
        },
        {
            'name': 'Local y Propify marcados',
            'params': {'fuente_local': 'local', 'fuente_propify': 'propify'},
            'expected': (True, False, True)
        },
        {
            'name': 'Todos marcados explícitamente',
            'params': {'fuente_local': 'local', 'fuente_externa': 'externa', 'fuente_propify': 'propify'},
            'expected': (True, True, True)
        },
        {
            'name': 'Con otros parámetros de filtro pero sin checkboxes',
            'params': {'tipo_propiedad': 'casa', 'departamento': 'Arequipa'},
            'expected': (True, True, True)
        },
        {
            'name': 'Con otros parámetros y solo Propify marcado',
            'params': {'tipo_propiedad': 'casa', 'fuente_propify': 'propify'},
            'expected': (False, False, True)
        },
    ]
    
    print("=== PRUEBAS DE LÓGICA DE CHECKBOXES ===\n")
    
    for test_case in test_cases:
        # Crear request con parámetros GET
        request = factory.get('/ingestas/propiedades/', data=test_case['params'])
        
        # Crear instancia de la vista
        view = ListaPropiedadesView()
        view.request = request
        
        # Llamar al método _calcular_checkboxes
        fuente_local, fuente_externa, fuente_propify = view._calcular_checkboxes()
        
        # Verificar resultados
        resultado = (fuente_local, fuente_externa, fuente_propify)
        esperado = test_case['expected']
        
        status = "OK" if resultado == esperado else "ERROR"
        
        print(f"{status} {test_case['name']}")
        print(f"  Parámetros: {test_case['params']}")
        print(f"  Esperado: Local={esperado[0]}, Externa={esperado[1]}, Propify={esperado[2]}")
        print(f"  Obtenido: Local={resultado[0]}, Externa={resultado[1]}, Propify={resultado[2]}")
        print()

def test_obtener_propiedades():
    """Prueba la obtención de propiedades con diferentes filtros."""
    
    factory = RequestFactory()
    
    print("=== PRUEBAS DE OBTENCIÓN DE PROPIEDADES ===\n")
    
    # Test 1: Sin filtros (debería mostrar todas)
    print("Test 1: Sin filtros (debería mostrar todas las fuentes)")
    request = factory.get('/ingestas/propiedades/', data={})
    view = ListaPropiedadesView()
    view.request = request
    todas_propiedades = view._obtener_todas_propiedades()
    
    # Contar por tipo
    locales = sum(1 for p in todas_propiedades if not p.get('es_externo') and not p.get('es_propify'))
    externas = sum(1 for p in todas_propiedades if p.get('es_externo') and not p.get('es_propify'))
    propify = sum(1 for p in todas_propiedades if p.get('es_propify'))
    
    print(f"  Total propiedades: {len(todas_propiedades)}")
    print(f"  Locales: {locales}, Externas: {externas}, Propify: {propify}")
    print()
    
    # Test 2: Solo Propify
    print("Test 2: Solo Propify marcado")
    request = factory.get('/ingestas/propiedades/', data={'fuente_propify': 'propify'})
    view = ListaPropiedadesView()
    view.request = request
    todas_propiedades = view._obtener_todas_propiedades()
    
    locales = sum(1 for p in todas_propiedades if not p.get('es_externo') and not p.get('es_propify'))
    externas = sum(1 for p in todas_propiedades if p.get('es_externo') and not p.get('es_propify'))
    propify = sum(1 for p in todas_propiedades if p.get('es_propify'))
    
    print(f"  Total propiedades: {len(todas_propiedades)}")
    print(f"  Locales: {locales}, Externas: {externas}, Propify: {propify}")
    print(f"  ¿Solo Propify?: {'Sí' if propify > 0 and locales == 0 and externas == 0 else 'No'}")
    print()

if __name__ == '__main__':
    test_checkbox_logic()
    test_obtener_propiedades()