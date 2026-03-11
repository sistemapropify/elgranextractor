#!/usr/bin/env python
"""
Prueba la vista ListaRequerimientosView usando Django test client.
"""
import os
import sys

# Asegurar que el directorio padre está en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from django.test import Client

def main():
    client = Client()
    response = client.get('/requerimientos/lista/')
    
    print(f'Status code: {response.status_code}')
    if response.status_code == 200:
        print('SUCCESS: Vista carga correctamente')
        content = response.content.decode('utf-8')
        # Verificaciones básicas
        checks = [
            ('Lista de Requerimientos', 'Título'),
            ('Grupo WhatsApp', 'Encabezado Grupo WhatsApp'),
            ('table', 'Tabla HTML'),
            ('Filtros', 'Sección de filtros'),
        ]
        for text, desc in checks:
            if text in content:
                print(f'✓ {desc} encontrado')
            else:
                print(f'✗ {desc} NO encontrado')
        
        # Verificar que no hay errores de template
        if 'error' in content.lower() or 'exception' in content.lower():
            print('WARNING: Posible error en template')
            # Extraer líneas con error
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'error' in line.lower() or 'exception' in line.lower():
                    print(f'   Línea {i}: {line.strip()[:100]}')
        else:
            print('✓ No se detectaron errores en el template')
        
        # Contar requerimientos en la tabla
        from requerimientos.models import Requerimiento
        count = Requerimiento.objects.count()
        print(f'Total de requerimientos en BD: {count}')
        
        # Verificar que la tabla tiene filas (si hay datos)
        if count > 0:
            if '<tr>' in content and '<td>' in content:
                print('✓ Tabla contiene filas')
            else:
                print('✗ Tabla parece vacía')
        
        return True
    else:
        print('ERROR: Vista no carga')
        print('Contenido de error:', response.content[:1000])
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)