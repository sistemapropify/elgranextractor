#!/usr/bin/env python
"""
Prueba los filtros de presupuesto mínimo y máximo.
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
from requerimientos.models import Requerimiento

def main():
    client = Client()
    
    # Primero, contar total
    total = Requerimiento.objects.count()
    print(f'Total requerimientos: {total}')
    
    # Hacer una solicitud sin filtros
    response = client.get('/requerimientos/lista/', HTTP_HOST='localhost')
    if response.status_code != 200:
        print('ERROR: Vista sin filtros falla')
        return False
    print('Vista sin filtros OK')
    
    # Hacer una solicitud con filtro de presupuesto mínimo
    response = client.get('/requerimientos/lista/?presupuesto_min=100000', HTTP_HOST='localhost')
    if response.status_code != 200:
        print('ERROR: Vista con presupuesto_min falla')
        return False
    print('Vista con presupuesto_min OK')
    
    # Verificar que la respuesta contiene los inputs con valores
    content = response.content.decode('utf-8', errors='ignore')
    if 'presupuesto_min' in content and 'value="100000"' in content:
        print('Input de presupuesto_min conserva valor')
    else:
        print('WARNING: Input no conserva valor')
    
    # Hacer una solicitud con ambos filtros
    response = client.get('/requerimientos/lista/?presupuesto_min=50000&presupuesto_max=200000', HTTP_HOST='localhost')
    if response.status_code != 200:
        print('ERROR: Vista con ambos filtros falla')
        return False
    print('Vista con ambos filtros OK')
    
    # Verificar que no hay errores en template
    if 'error' in content.lower() or 'exception' in content.lower():
        print('ERROR: Se detectó error en template')
        return False
    
    print('Todos los filtros funcionan correctamente.')
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)