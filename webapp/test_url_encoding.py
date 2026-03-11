#!/usr/bin/env python
import os
import sys
import django
import urllib.parse

# Agregar el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropertyImage

# Obtener imagen con caracteres especiales
imgs = PropertyImage.objects.filter(image__contains='Informaci')
for img in imgs[:3]:
    print('Original image field:', repr(img.image))
    # Codificar cada segmento de la ruta
    parts = img.image.split('/')
    encoded_parts = [urllib.parse.quote(part) for part in parts]
    encoded_path = '/'.join(encoded_parts)
    print('Encoded path:', encoded_path)
    url = 'https://propifymedia01.blob.core.windows.net/media/' + encoded_path
    print('URL:', url)
    print()