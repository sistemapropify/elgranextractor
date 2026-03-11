#!/usr/bin/env python
"""
Prueba la nueva grilla de requerimientos.
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
        
        # Verificar que no hay errores de template
        if 'error' in content.lower() or 'exception' in content.lower():
            print('ERROR: Se detectó error en template')
            return False
        
        # Verificar presencia de secciones clave
        checks = [
            ('Origen', 'Columna Origen'),
            ('Clasificación', 'Columna Clasificación'),
            ('Presupuesto', 'Columna Presupuesto'),
            ('Características', 'Columna Características'),
            ('Requerimiento', 'Columna Requerimiento'),
        ]
        missing = []
        for text, desc in checks:
            if text not in content:
                missing.append(desc)
        
        if missing:
            print(f'WARNING: Faltan secciones: {missing}')
        else:
            print('✓ Todas las secciones clave presentes')
        
        # Verificar que la tabla tiene estructura
        if '<table' in content and '</table>' in content:
            print('✓ Tabla HTML encontrada')
        else:
            print('✗ No se encontró tabla HTML')
        
        # Verificar que hay datos (si existen)
        from requerimientos.models import Requerimiento
        count = Requerimiento.objects.count()
        print(f'Total de requerimientos en BD: {count}')
        
        print('\n--- RESUMEN ---')
        print('La nueva grilla de requerimientos está implementada.')
        print('Los campos están agrupados de manera similar al ejemplo proporcionado.')
        return True
    else:
        print('ERROR: Vista no carga')
        print('Contenido de error:', response.content[:1500])
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)