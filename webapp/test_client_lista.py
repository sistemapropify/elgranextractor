#!/usr/bin/env python
"""
Prueba de la vista ListaRequerimientosView usando Django test client.
"""
import os
import sys
import django

# Añadir el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import Client

def test_view():
    client = Client()
    response = client.get('/requerimientos/lista/')
    
    print(f'Status code: {response.status_code}')
    if response.status_code != 200:
        print(f'ERROR: Status code {response.status_code}')
        print('Contenido:', response.content[:500])
        return False
    
    # Verificar que la respuesta contiene elementos esperados
    content = response.content.decode('utf-8')
    if 'Lista de Requerimientos' in content:
        print('✓ Título encontrado')
    if 'Grupo WhatsApp' in content:
        print('✓ Encabezado Grupo WhatsApp encontrado')
    if 'table' in content:
        print('✓ Tabla encontrada')
    
    # Contar requerimientos mostrados
    from requerimientos.models import Requerimiento
    total = Requerimiento.objects.count()
    print(f'Total de requerimientos en BD: {total}')
    
    # Verificar que no hay errores de template
    if 'error' in content.lower() or 'exception' in content.lower():
        print('✗ Posible error en template')
        print('Fragmento de error:', content[content.find('error'):content.find('error')+200])
        return False
    
    print('SUCCESS: Vista funciona correctamente')
    return True

if __name__ == '__main__':
    success = test_view()
    sys.exit(0 if success else 1)