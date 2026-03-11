#!/usr/bin/env python
"""
Script para probar la renderización del template lista_propiedades.html
"""
import os
import sys
import django
from django.template import Template, Context

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw

def test_template():
    """Prueba renderizar el template con datos de ejemplo"""
    try:
        # Leer el template
        template_path = os.path.join('templates', 'ingestas', 'lista_propiedades.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Crear contexto de prueba
        context = Context({
            'propiedades': PropiedadRaw.objects.all()[:5],  # Primeras 5 propiedades
            'page_obj': None,
            'is_paginated': False,
        })
        
        # Renderizar
        template = Template(template_content)
        rendered = template.render(context)
        
        print("✅ Template renderizado exitosamente")
        print(f"Longitud del HTML generado: {len(rendered)} caracteres")
        
        # Verificar elementos clave
        if 'Portal Inmobiliario' in rendered:
            print("✅ Título 'Portal Inmobiliario' encontrado")
        if 'googleMap' in rendered:
            print("✅ Mapa de Google encontrado")
        if 'property-card' in rendered:
            print("✅ Tarjetas de propiedades encontradas")
        
        return True
    except Exception as e:
        print(f"❌ Error al renderizar template: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("Probando renderización del template lista_propiedades.html...")
    success = test_template()
    sys.exit(0 if success else 1)