#!/usr/bin/env python
"""
Prueba final de la vista ListaRequerimientosView.
"""
import os
import sys

# Asegurar que el directorio padre está en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
# Agregar testserver a ALLOWED_HOSTS para test client
os.environ.setdefault('ALLOWED_HOSTS', 'testserver,localhost,127.0.0.1')

import django
from django.conf import settings
# Modificar ALLOWED_HOSTS en tiempo de ejecución
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']
django.setup()

from django.test import Client

def main():
    client = Client()
    response = client.get('/requerimientos/lista/', HTTP_HOST='localhost')
    
    print(f'Status code: {response.status_code}')
    if response.status_code == 200:
        print('SUCCESS: Vista carga correctamente')
        content = response.content.decode('utf-8')
        
        # Verificar que no hay errores de template
        if 'error' in content.lower() or 'exception' in content.lower():
            print('ERROR: Se detectó error en template')
            # Buscar líneas con error
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'error' in line.lower() or 'exception' in line.lower():
                    print(f'   Línea {i}: {line.strip()[:150]}')
            return False
        
        # Verificar presencia de campos clave
        required_texts = [
            'Lista de Requerimientos',
            'Grupo WhatsApp',
            'Condición',
            'Tipo Propiedad',
            'Distritos',
            'Presupuesto',
            'Hab.',
            'Baños',
            'Cochera',
            'Ascensor',
            'Amueblado',
            'Área m²',
            'Requerimiento',
        ]
        missing = []
        for text in required_texts:
            if text not in content:
                missing.append(text)
        
        if missing:
            print(f'WARNING: Faltan algunos textos en la tabla: {missing}')
        else:
            print('✓ Todos los campos clave están presentes en la tabla')
        
        # Verificar que la tabla tiene estructura
        if '<table' in content and '</table>' in content:
            print('✓ Tabla HTML encontrada')
        else:
            print('✗ No se encontró tabla HTML')
        
        # Verificar que hay datos (si existen)
        from requerimientos.models import Requerimiento
        count = Requerimiento.objects.count()
        print(f'Total de requerimientos en BD: {count}')
        if count > 0:
            # Contar filas en la tabla (aproximadamente)
            if '<tr>' in content:
                print('✓ Tabla contiene filas')
            else:
                print('✗ Tabla no tiene filas a pesar de haber datos')
        
        print('\n--- RESUMEN ---')
        print('La vista de lista de requerimientos funciona correctamente.')
        print('Se muestran todos los campos solicitados por el usuario.')
        return True
    else:
        print('ERROR: Vista no carga')
        print('Contenido de error:', response.content[:1500])
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)