import sys
import os
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    import django
    django.setup()
except Exception as e:
    print(f'Error setup Django: {e}')
    sys.exit(1)

from django.test import Client

client = Client()
response = client.get('/requerimientos/lista/')
print(f'Status: {response.status_code}')
if response.status_code == 200:
    print('Vista funciona')
    content = response.content.decode('utf-8')
    if 'Lista de Requerimientos' in content:
        print('Título OK')
    if 'Grupo WhatsApp' in content:
        print('Encabezado OK')
    # Verificar que no hay errores
    if 'error' in content.lower():
        print('ERROR encontrado en contenido')
        # Buscar línea con error
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'error' in line.lower():
                print(f'Línea {i}: {line[:200]}')
    else:
        print('No se detectaron errores en el contenido')
else:
    print('Error status:', response.status_code)
    print('Contenido:', response.content[:1000])