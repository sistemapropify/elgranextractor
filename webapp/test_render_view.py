#!/usr/bin/env python
"""
Script para probar el renderizado de la vista dashboard_eventos.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from eventos.views import dashboard_eventos

def test_view_render():
    print("=== Prueba de renderizado de vista dashboard_eventos ===")
    
    # Crear una solicitud simulada
    factory = RequestFactory()
    request = factory.get('/eventos/')
    
    # Configurar ALLOWED_HOSTS para evitar errores
    from django.conf import settings
    settings.ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
    
    try:
        # Ejecutar la vista
        response = dashboard_eventos(request)
        print(f"Status Code: {response.status_code}")
        print(f"Content Type: {response['Content-Type']}")
        
        if response.status_code == 200:
            print("OK: Vista renderizada exitosamente")
            
            # Verificar contenido básico
            content = response.content.decode('utf-8')
            
            # Verificar que no haya errores en el template
            if 'Error' in content or 'Exception' in content or 'Traceback' in content:
                print("ERROR: Se detectaron errores en el contenido")
                # Buscar líneas con error
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'Error' in line or 'Exception' in line:
                        print(f"  Línea {i}: {line[:200]}")
                return False
            else:
                print("OK: No se detectaron errores en el template")
                
            # Verificar elementos esperados
            expected_elements = [
                'Eventos',
                'Filtrar',
                'Propiedad',
                'Coordenadas',
                'mapModal'
            ]
            
            for element in expected_elements:
                if element in content:
                    print(f"OK: Elemento '{element}' encontrado")
                else:
                    print(f"WARNING: Elemento '{element}' NO encontrado")
            
            return True
        else:
            print(f"ERROR: Código de estado {response.status_code}")
            print(f"Contenido: {response.content[:500]}")
            return False
            
    except Exception as e:
        print(f"ERROR al ejecutar la vista: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_view_render()
    print("\n" + "="*50)
    if success:
        print("PRUEBA EXITOSA: La vista se renderiza correctamente")
        sys.exit(0)
    else:
        print("PRUEBA FALLIDA: Hay problemas con la vista")
        sys.exit(1)