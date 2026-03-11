import os
import sys

# Cambiar al directorio correcto
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Configurar Django
sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from django.template.loader import render_to_string
from django.test import RequestFactory

print("Probando renderizado del template...")

factory = RequestFactory()
request = factory.get('/ingestas/propiedades/')

context = {
    'propiedades': [],
    'page_obj': None,
    'is_paginated': False,
    'request': request,
}

try:
    html = render_to_string('ingestas/lista_propiedades.html', context)
    print("SUCCESS: Template renderizado exitosamente")
    print(f"Longitud HTML: {len(html)} caracteres")
    
    # Verificaciones básicas
    checks = [
        ('Portal Inmobiliario', 'Título del portal'),
        ('googleMap', 'Mapa de Google'),
        ('NUEVO', 'Badge NUEVO'),
        ('No hay propiedades disponibles', 'Mensaje sin propiedades'),
        ('AIzaSyBrL1QF7vTl9zF8FmCUumfRpFJcaYokO7Q', 'API Key de Google Maps'),
    ]
    
    for text, description in checks:
        if text in html:
            print(f"  ✓ {description} encontrado")
        else:
            print(f"  ✗ {description} NO encontrado")
    
    # Guardar una muestra
    sample = html[:1500]
    with open('template_sample.html', 'w', encoding='utf-8') as f:
        f.write(sample)
    print(f"Muestra guardada en template_sample.html (1500 caracteres)")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()