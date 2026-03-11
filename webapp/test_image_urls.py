#!/usr/bin/env python
"""
Script para verificar si las URLs de imágenes en Azure Storage son accesibles.
"""
import os
import sys
import requests
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from propifai.models import PropifaiProperty

def test_image_access():
    """Prueba el acceso a algunas URLs de imágenes."""
    print("Verificando acceso a URLs de imágenes...")
    print("-" * 80)
    
    # Obtener algunas propiedades
    propiedades = PropifaiProperty.objects.all()[:3]
    
    if not propiedades:
        print("No se encontraron propiedades.")
        return
    
    for i, propiedad in enumerate(propiedades):
        url = propiedad.imagen_url
        print(f"\nPropiedad {i+1}: {propiedad.code}")
        print(f"  URL: {url}")
        
        if not url:
            print("  [ERROR] No hay URL de imagen")
            continue
        
        try:
            # Hacer una solicitud HEAD para verificar si la imagen existe
            response = requests.head(url, timeout=5)
            if response.status_code == 200:
                print(f"  [OK] Imagen accesible (status: {response.status_code})")
                # Mostrar información del contenido
                content_type = response.headers.get('Content-Type', 'desconocido')
                content_length = response.headers.get('Content-Length', 'desconocido')
                print(f"     Tipo: {content_type}, Tamaño: {content_length} bytes")
            elif response.status_code == 404:
                print(f"  [ERROR] Imagen no encontrada (404)")
                # Probar con otras extensiones
                test_alternative_extensions(propiedad.code)
            else:
                print(f"  [WARNING] Status inesperado: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  [ERROR] Error al acceder a la URL: {e}")
            print(f"     Posiblemente la imagen no existe o hay problemas de red.")
    
    # Probar también con algunas URLs directas
    print("\n" + "=" * 80)
    print("Pruebas con URLs directas:")
    test_urls = [
        "https://propifymedia01.blob.core.windows.net/media/PROP000001.jpg",
        "https://propifymedia01.blob.core.windows.net/media/PROP000002.jpg",
        "https://propifymedia01.blob.core.windows.net/media/PROP000003.jpg",
    ]
    
    for url in test_urls:
        try:
            response = requests.head(url, timeout=5)
            print(f"\n{url}")
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                print(f"  [OK] Accesible")
            elif response.status_code == 404:
                print(f"  [ERROR] No encontrada")
            else:
                print(f"  [WARNING] {response.status_code}")
        except Exception as e:
            print(f"\n{url}")
            print(f"  [ERROR] Error: {e}")

def test_alternative_extensions(code):
    """Prueba diferentes extensiones para una propiedad."""
    base_url = "https://propifymedia01.blob.core.windows.net/media"
    extensions = ['.jpg', '.jpeg', '.png', '.webp']
    
    print(f"  Probando extensiones alternativas para {code}:")
    for ext in extensions:
        url = f"{base_url}/{code}{ext}"
        try:
            response = requests.head(url, timeout=3)
            if response.status_code == 200:
                print(f"    [OK] {ext}: Encontrada")
                return url
            else:
                print(f"    [ERROR] {ext}: No encontrada (status: {response.status_code})")
        except:
            print(f"    [ERROR] {ext}: Error de conexión")
    return None

if __name__ == '__main__':
    test_image_access()