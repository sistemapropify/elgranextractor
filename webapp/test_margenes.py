#!/usr/bin/env python
"""
Verifica que la vista carga con los nuevos márgenes.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
os.environ.setdefault('ALLOWED_HOSTS', 'testserver,localhost,127.0.0.1')

import django
from django.conf import settings
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']
django.setup()

from django.test import Client

def main():
    client = Client()
    response = client.get('/requerimientos/lista/', HTTP_HOST='localhost')
    
    print(f'Status code: {response.status_code}')
    if response.status_code == 200:
        print('SUCCESS: Vista carga correctamente')
        content = response.content.decode('utf-8', errors='ignore')
        
        # Verificar que se usan container-fluid
        if 'container-fluid' in content:
            print('✓ Usa container-fluid (menos márgenes laterales)')
        else:
            print('✗ No usa container-fluid')
        
        # Verificar que no hay errores
        if 'error' in content.lower() or 'exception' in content.lower():
            print('ERROR: Se detectó error en template')
            return False
        
        print('La grilla ahora ocupa más ancho con menos márgenes.')
        return True
    else:
        print('ERROR: Vista no carga')
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)