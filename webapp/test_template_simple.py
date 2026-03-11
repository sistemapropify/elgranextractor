#!/usr/bin/env python
"""
Prueba simple de renderizado de template sin dependencias complejas.
"""
import os
import sys

# Añadir el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar Django manualmente
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    import django
    django.setup()
    
    from django.template.loader import render_to_string
    from django.test import RequestFactory
    
    # Crear un request simulado
    factory = RequestFactory()
    request = factory.get('/ingestas/propiedades/')
    
    # Contexto de prueba
    context = {
        'propiedades': [],  # Lista vacía para probar el caso sin propiedades
        'page_obj': None,
        'is_paginated': False,
        'request': request,
    }
    
    # Renderizar el template
    try:
        html = render_to_string('ingestas/lista_propiedades.html', context)
        print("✅ Template renderizado exitosamente!")
        print(f"Longitud del HTML: {len(html)} caracteres")
        
        # Verificar elementos clave
        if 'Portal Inmobiliario' in html:
            print("✅ Título 'Portal Inmobiliario' encontrado")
        if 'googleMap' in html:
            print("✅ Mapa de Google encontrado")
        if 'No hay propiedades disponibles' in html:
            print("✅ Mensaje de 'No hay propiedades' encontrado (esperado para lista vacía)")
        if 'NUEVO' in html:
            print("✅ Badge 'NUEVO' encontrado")
            
        # Guardar una muestra para inspección
        with open('test_output.html', 'w', encoding='utf-8') as f:
            f.write(html[:2000])  # Primeros 2000 caracteres
        print("📄 Muestra guardada en test_output.html")
        
    except Exception as e:
        print(f"❌ Error al renderizar: {e}")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"❌ Error configurando Django: {e}")
    import traceback
    traceback.print_exc()