#!/usr/bin/env python
"""
Script para verificar que las URLs de imagen se generan correctamente
después de las correcciones aplicadas.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from propifai.models import PropifaiProperty

def test_imagenes():
    """Probar que las propiedades tienen URLs de imagen válidas."""
    print("=== PRUEBA DE URLs DE IMAGEN DESPUÉS DE CORRECCIONES ===")
    
    # Obtener algunas propiedades
    propiedades = PropifaiProperty.objects.using('propifai').all()[:10]
    
    print(f"Total de propiedades encontradas: {len(propiedades)}")
    print()
    
    for i, p in enumerate(propiedades):
        print(f"Propiedad {i+1}: ID={p.id}, Código={p.codigo}")
        print(f"  imagen_url: {p.imagen_url}")
        print(f"  primera_imagen_url: {p.primera_imagen_url}")
        
        # Verificar si la URL es válida
        if p.imagen_url:
            print(f"  ✓ Tiene URL de imagen")
            # Verificar si la URL contiene caracteres problemáticos
            if '�' in p.imagen_url:
                print(f"  ⚠️  URL contiene caracteres problemáticos")
            else:
                print(f"  ✓ URL parece válida")
        else:
            print(f"  ✗ No tiene URL de imagen")
        
        # Mostrar imágenes relacionadas
        imagenes = p.imagenes_relacionadas
        print(f"  Imágenes relacionadas: {len(imagenes)}")
        for j, img in enumerate(imagenes[:3]):  # Mostrar solo las primeras 3
            print(f"    - {img}")
        
        print()

def test_vista_context():
    """Probar que el contexto de la vista incluye las URLs correctas."""
    print("\n=== PRUEBA DE CONTEXTO DE VISTA ===")
    
    from propifai.views import ListaPropiedadesPropifyView
    from django.test import RequestFactory
    
    # Crear una solicitud simulada
    factory = RequestFactory()
    request = factory.get('/propifai/propiedades/')
    
    # Crear la vista
    view = ListaPropiedadesPropifyView()
    view.request = request
    
    # Obtener el contexto
    context = view.get_context_data()
    
    print(f"Contexto generado:")
    print(f"  - object_list: {len(context.get('object_list', []))} propiedades")
    
    # Verificar una propiedad del contexto
    if context.get('object_list'):
        primera_prop = context['object_list'][0]
        print(f"\nPrimera propiedad en contexto:")
        print(f"  - ID: {primera_prop.get('id')}")
        print(f"  - imagen_url: {primera_prop.get('imagen_url')}")
        print(f"  - primera_imagen: {primera_prop.get('primera_imagen')}")

if __name__ == '__main__':
    test_imagenes()
    test_vista_context()