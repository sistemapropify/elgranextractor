#!/usr/bin/env python
"""
Script para probar la generación de URLs de imágenes de Propify.
"""
import os
import sys
import django

# Agregar el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty, PropertyImage

def main():
    print("=== PRUEBA DE IMÁGENES PROPIFY ===\n")
    
    # Obtener una propiedad
    prop = PropifaiProperty.objects.first()
    if not prop:
        print("No hay propiedades en la base de datos.")
        return
    
    print(f"Propiedad: {prop.code} (ID: {prop.id})")
    print(f"imagen_url: {prop.imagen_url}")
    print(f"primera_imagen_url: {prop.primera_imagen_url}")
    
    # Verificar imágenes relacionadas
    imagenes = prop.imagenes_relacionadas
    print(f"\nNúmero de imágenes relacionadas: {imagenes.count()}")
    for i, img in enumerate(imagenes[:3]):
        print(f"  Imagen {i+1}:")
        print(f"    ID: {img.id}")
        print(f"    property_id: {img.property_id}")
        print(f"    image: {img.image}")
        print(f"    URL convertida: {prop._convertir_a_url_azure(img.image)}")
    
    # Verificar si hay datos en property_images
    total_imagenes = PropertyImage.objects.count()
    print(f"\nTotal de imágenes en property_images: {total_imagenes}")
    if total_imagenes > 0:
        sample = PropertyImage.objects.first()
        print(f"Ejemplo: property_id={sample.property_id}, image={sample.image}")
    
    # Probar con varias propiedades
    print("\n=== PRUEBA CON 5 PROPIEDADES ===")
    propiedades = PropifaiProperty.objects.all()[:5]
    for p in propiedades:
        print(f"\nPropiedad: {p.code} (ID: {p.id})")
        print(f"  imagen_url: {p.imagen_url}")
        print(f"  tiene imágenes relacionadas: {p.imagenes_relacionadas.count()}")
        if p.imagenes_relacionadas.count() > 0:
            primera = p.imagenes_relacionadas.first()
            print(f"  primera imagen: {primera.image}")
            print(f"  URL: {p._convertir_a_url_azure(primera.image)}")

if __name__ == '__main__':
    main()