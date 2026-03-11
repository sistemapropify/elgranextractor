import os
import sys

# Añadir el directorio actual al path
sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from propifai.models import PropifaiProperty

print('=== PRUEBA RÁPIDA DE IMÁGENES ===')
propiedades = PropifaiProperty.objects.using('propifai').all()[:5]

for p in propiedades:
    print(f'ID: {p.id}, Código: {p.codigo}')
    print(f'  imagen_url: {p.imagen_url}')
    print(f'  primera_imagen_url: {p.primera_imagen_url}')
    
    # Verificar si tiene imágenes relacionadas
    imagenes = p.imagenes_relacionadas
    print(f'  Imágenes relacionadas: {len(imagenes)}')
    if imagenes:
        print(f'    Primera imagen: {imagenes[0]}')
    
    print()