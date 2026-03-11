#!/usr/bin/env python
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty, PropertyImage

print("=== RELACIÓN ENTRE PropifaiProperty Y PropertyImage ===\n")

# Tomar algunas propiedades
props = PropifaiProperty.objects.all()[:10]
for prop in props:
    print(f"Propiedad ID: {prop.id}, Código: {prop.code}")
    imagenes = prop.imagenes_relacionadas
    print(f"  Número de imágenes relacionadas: {imagenes.count()}")
    for img in imagenes[:2]:
        print(f"    - PropertyImage ID: {img.id}, property_id: {img.property_id}, image: {img.image}")
        print(f"      URL generada: {prop._convertir_a_url_azure(img.image)}")
    if imagenes.count() == 0:
        print("    (No hay imágenes relacionadas)")
    print()

# Verificar si hay property_ids que no coinciden
print("\n=== VERIFICACIÓN DE COINCIDENCIAS ===\n")
all_images = PropertyImage.objects.all()[:20]
for img in all_images:
    try:
        prop = PropifaiProperty.objects.get(id=img.property_id)
        print(f"PropertyImage property_id={img.property_id} -> PropifaiProperty id={prop.id} (Código: {prop.code})")
    except PropifaiProperty.DoesNotExist:
        print(f"PropertyImage property_id={img.property_id} -> NO EXISTE PropifaiProperty con ese id")
    except Exception as e:
        print(f"Error: {e}")