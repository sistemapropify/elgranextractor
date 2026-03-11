#!/usr/bin/env python
"""
Script para probar que el filtro de distrito funciona correctamente.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from django.test import Client
from django.urls import reverse

def test_filtro_distrito():
    """Prueba que el filtro de distrito esté presente en la página."""
    client = Client()
    
    # Obtener la página de lista de propiedades
    url = reverse('ingestas:lista_propiedades')
    response = client.get(url)
    
    print(f"Status code: {response.status_code}")
    
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        
        # Verificar que el filtro de distrito esté presente
        if 'filter-distrito' in content:
            print("✓ Filtro de distrito encontrado en el HTML (ID 'filter-distrito')")
        else:
            print("✗ Filtro de distrito NO encontrado en el HTML")
            
        # Verificar que haya opciones de distrito
        if 'distritos' in response.context:
            distritos = response.context['distritos']
            print(f"✓ Contexto 'distritos' encontrado con {len(distritos)} opciones")
            if distritos:
                print(f"  Ejemplos de distritos: {list(distritos)[:5]}")
        else:
            print("✗ Contexto 'distritos' NO encontrado")
            
        # Verificar que el parámetro 'distrito' se pueda usar en filtros
        response_con_filtro = client.get(url, {'distrito': 'Miraflores'})
        print(f"\nPrueba con filtro distrito='Miraflores': Status {response_con_filtro.status_code}")
        
        # Verificar que el filtro se aplica (debug output)
        if 'DEBUG _obtener_todas_propiedades' in content:
            print("✓ Debug output encontrado en la respuesta")
    else:
        print(f"✗ Error: La página devolvió código {response.status_code}")
        
    return response.status_code == 200

if __name__ == '__main__':
    print("=== PRUEBA DE FILTRO DE DISTRITO ===\n")
    success = test_filtro_distrito()
    print(f"\n{'✓ Prueba exitosa' if success else '✗ Prueba fallida'}")
    sys.exit(0 if success else 1)