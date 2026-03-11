#!/usr/bin/env python
"""
Script para probar la respuesta HTTP de la vista con diferentes parámetros.
"""

import os
import sys
import django
from django.test import Client

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

# Configurar ALLOWED_HOSTS para pruebas
from django.conf import settings
settings.ALLOWED_HOSTS.append('testserver')

def test_http_responses():
    """Prueba las respuestas HTTP con diferentes parámetros GET."""
    
    client = Client()
    
    test_cases = [
        {
            'name': 'Sin parámetros',
            'params': {},
            'expected_checkboxes': {'local': True, 'externa': True, 'propify': True}
        },
        {
            'name': 'Solo Propify',
            'params': {'fuente_propify': 'propify'},
            'expected_checkboxes': {'local': False, 'externa': False, 'propify': True}
        },
        {
            'name': 'Solo Locales',
            'params': {'fuente_local': 'local'},
            'expected_checkboxes': {'local': True, 'externa': False, 'propify': False}
        },
        {
            'name': 'Locales y Externas',
            'params': {'fuente_local': 'local', 'fuente_externa': 'externa'},
            'expected_checkboxes': {'local': True, 'externa': True, 'propify': False}
        },
    ]
    
    print("=== PRUEBAS HTTP DE FILTROS ===\n")
    
    for test_case in test_cases:
        print(f"Test: {test_case['name']}")
        print(f"Parámetros: {test_case['params']}")
        
        # Hacer solicitud GET
        response = client.get('/ingestas/propiedades/', data=test_case['params'])
        
        if response.status_code == 200:
            # Verificar contenido HTML
            content = response.content.decode('utf-8', errors='ignore')
            
            # Buscar checkboxes en el HTML
            checkbox_local_checked = 'id="filter-fuente-local"' in content and 'checked' in content[content.find('id="filter-fuente-local"'):content.find('id="filter-fuente-local"')+200]
            checkbox_externa_checked = 'id="filter-fuente-externa"' in content and 'checked' in content[content.find('id="filter-fuente-externa"'):content.find('id="filter-fuente-externa"')+200]
            checkbox_propify_checked = 'id="filter-fuente-propify"' in content and 'checked' in content[content.find('id="filter-fuente-propify"'):content.find('id="filter-fuente-propify"')+200]
            
            print(f"  Checkbox Local: {'checked' if checkbox_local_checked else 'unchecked'}")
            print(f"  Checkbox Externa: {'checked' if checkbox_externa_checked else 'unchecked'}")
            print(f"  Checkbox Propify: {'checked' if checkbox_propify_checked else 'unchecked'}")
            
            # Verificar conteos
            import re
            conteo_match = re.search(r'\((\d+) locales \+ (\d+) externas \+ (\d+) propify\)', content)
            if conteo_match:
                locales = int(conteo_match.group(1))
                externas = int(conteo_match.group(2))
                propify = int(conteo_match.group(3))
                print(f"  Conteos: Locales={locales}, Externas={externas}, Propify={propify}")
            
            # Verificar propiedades Propify en el HTML
            propify_count = content.count('data-es-propify="true"')
            print(f"  Propiedades Propify en HTML: {propify_count}")
            
            # Verificar si los checkboxes coinciden con lo esperado
            expected = test_case['expected_checkboxes']
            actual = {
                'local': checkbox_local_checked,
                'externa': checkbox_externa_checked,
                'propify': checkbox_propify_checked
            }
            
            if actual == expected:
                print("  OK Checkboxes correctos")
            else:
                print(f"  ERROR Checkboxes incorrectos. Esperado: {expected}, Obtenido: {actual}")
            
        else:
            print(f"  ✗ Error HTTP: {response.status_code}")
        
        print()

if __name__ == '__main__':
    test_http_responses()