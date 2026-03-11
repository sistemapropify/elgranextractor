#!/usr/bin/env python
"""
Script para probar que las URLs de imágenes sean completas y accesibles.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from propifai.models import PropifaiProperty
import requests

def test_urls_completas():
    """Prueba que las URLs de imágenes sean completas y accesibles."""
    print("Probando URLs completas de imágenes...")
    print("=" * 80)
    
    # Obtener algunas propiedades
    propiedades = PropifaiProperty.objects.all()[:3]
    
    for i, propiedad in enumerate(propiedades):
        print(f"\nPropiedad {i+1}: {propiedad.code}")
        print(f"  imagen_url: {propiedad.imagen_url}")
        
        # Verificar si la URL es accesible
        if propiedad.imagen_url:
            try:
                response = requests.head(propiedad.imagen_url, timeout=5)
                print(f"  Status HTTP: {response.status_code}")
                if response.status_code == 200:
                    print(f"  [OK] Imagen accesible")
                    # Mostrar tipo de contenido
                    content_type = response.headers.get('Content-Type', 'desconocido')
                    print(f"  Tipo: {content_type}")
                elif response.status_code == 404:
                    print(f"  [ERROR] Imagen no encontrada (404)")
                    # Probar si la ruta relativa necesita ajustes
                    print(f"  Probando variaciones...")
                    test_variaciones_url(propiedad.imagen_url)
                else:
                    print(f"  [WARNING] Status inesperado: {response.status_code}")
            except Exception as e:
                print(f"  [ERROR] Error al acceder: {e}")
        else:
            print(f"  [WARNING] No hay URL de imagen")
    
    # Probar conversión de rutas
    print("\n" + "=" * 80)
    print("Prueba de conversión de rutas:")
    test_rutas = [
        "properties/images/Mesa_de_trabajo_1_6_9ReWqhk.png",
        "/properties/images/archivo.jpg",
        "https://ejemplo.com/imagen.jpg",
        "imagenes/foto.png",
        None,
        ""
    ]
    
    for ruta in test_rutas:
        # Crear propiedad ficticia para probar el método
        class MockProp:
            def _convertir_a_url_azure(self, ruta_relativa):
                if not ruta_relativa:
                    return None
                if ruta_relativa.startswith(('http://', 'https://')):
                    return ruta_relativa
                base_url = "https://propifymedia01.blob.core.windows.net/media"
                if ruta_relativa.startswith('/'):
                    ruta_relativa = ruta_relativa[1:]
                return f"{base_url}/{ruta_relativa}"
        
        mock = MockProp()
        resultado = mock._convertir_a_url_azure(ruta)
        print(f"  '{ruta}' -> '{resultado}'")

def test_variaciones_url(url):
    """Prueba variaciones de la URL para encontrar la correcta."""
    # Si la URL ya es de Azure, probar variaciones
    if 'blob.core.windows.net' in url:
        # Intentar sin el prefijo 'media/' si está duplicado
        if '/media/media/' in url:
            nueva_url = url.replace('/media/media/', '/media/')
            print(f"    Probando: {nueva_url}")
            try:
                response = requests.head(nueva_url, timeout=3)
                if response.status_code == 200:
                    print(f"    [OK] Variación funciona: {response.status_code}")
                    return nueva_url
            except:
                pass
        
        # Intentar con diferentes contenedores
        contenedores = ['media', 'images', 'properties', 'propify']
        for cont in contenedores:
            if f'/{cont}/' in url:
                continue
            # Reemplazar 'media' por otro contenedor
            nueva_url = url.replace('blob.core.windows.net/media', f'blob.core.windows.net/{cont}')
            print(f"    Probando contenedor '{cont}': {nueva_url}")
            try:
                response = requests.head(nueva_url, timeout=2)
                if response.status_code == 200:
                    print(f"    [OK] Contenedor '{cont}' funciona")
                    return nueva_url
            except:
                pass
    
    return None

if __name__ == '__main__':
    test_urls_completas()