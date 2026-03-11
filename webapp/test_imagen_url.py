#!/usr/bin/env python
"""
Script para probar la propiedad imagen_url en el modelo PropifaiProperty.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from propifai.models import PropifaiProperty

def test_imagen_url():
    """Prueba la propiedad imagen_url con algunas propiedades de ejemplo."""
    print("Probando propiedad imagen_url...")
    print("-" * 80)
    
    # Obtener algunas propiedades de ejemplo
    propiedades = PropifaiProperty.objects.all()[:5]
    
    if not propiedades:
        print("No se encontraron propiedades en la base de datos.")
        return
    
    for i, propiedad in enumerate(propiedades):
        print(f"\nPropiedad {i+1}:")
        print(f"  Código: {propiedad.code}")
        print(f"  Título: {propiedad.title}")
        print(f"  imagen_url: {propiedad.imagen_url}")
        
        # También mostrar otras propiedades relevantes
        print(f"  Tipo (tipo_propiedad): {propiedad.tipo_propiedad}")
        print(f"  Precio: {propiedad.precio_formateado}")
        print(f"  Ubicación: {propiedad.ubicacion_completa}")
    
    # Probar con un código específico
    print("\n" + "=" * 80)
    print("Prueba con códigos específicos:")
    test_codes = ['PROP001', 'PROP002', 'ABC123', 'XYZ789']
    for code in test_codes:
        # Crear una propiedad ficticia para probar
        class MockProp:
            def __init__(self, code):
                self.code = code
        
        mock = MockProp(code)
        # Usar la lógica de imagen_url (copiada del modelo)
        if mock.code:
            base_url = "https://propifymedia01.blob.core.windows.net/media"
            extensions = ['.jpg', '.jpeg', '.png', '.webp']
            
            # Verificar si el código ya tiene extensión
            has_extension = False
            for ext in extensions:
                if mock.code.lower().endswith(ext):
                    has_extension = True
                    break
            
            if has_extension:
                url = f"{base_url}/{mock.code}"
            else:
                url = f"{base_url}/{mock.code}.jpg"
            
            print(f"  Código: {code} -> URL: {url}")

if __name__ == '__main__':
    test_imagen_url()