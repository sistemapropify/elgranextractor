#!/usr/bin/env python
"""
Script para probar la implementación completa de imágenes de Propify.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from propifai.models import PropifaiProperty, PropertyImage

def test_imagenes_implementation():
    """Prueba la implementación completa de imágenes."""
    print("Probando implementación de imágenes de Propify...")
    print("=" * 80)
    
    # 1. Verificar que los modelos se pueden importar
    print("1. Modelos importados correctamente:")
    print(f"   - PropifaiProperty: {PropifaiProperty}")
    print(f"   - PropertyImage: {PropertyImage}")
    
    # 2. Obtener algunas propiedades
    propiedades = PropifaiProperty.objects.all()[:5]
    print(f"\n2. Obteniendo {len(propiedades)} propiedades de ejemplo:")
    
    for i, propiedad in enumerate(propiedades):
        print(f"\n   Propiedad {i+1}:")
        print(f"     ID: {propiedad.id}")
        print(f"     Código: {propiedad.code}")
        print(f"     Título: {propiedad.title}")
        
        # 3. Probar propiedad imagen_url
        print(f"     imagen_url: {propiedad.imagen_url}")
        
        # 4. Probar imágenes relacionadas
        imagenes = propiedad.imagenes_relacionadas
        print(f"     Número de imágenes relacionadas: {imagenes.count()}")
        
        if imagenes.exists():
            for j, imagen in enumerate(imagenes[:2]):  # Mostrar solo las primeras 2
                print(f"       Imagen {j+1}: {imagen.image}")
                # Nota: el campo 'orden' no existe en el modelo actual
                # print(f"         Orden: {imagen.orden}")
        
        # 5. Probar primera_imagen_url
        print(f"     primera_imagen_url: {propiedad.primera_imagen_url}")
    
    # 6. Verificar algunas imágenes directamente
    print("\n3. Verificando imágenes directamente desde PropertyImage:")
    imagenes_directas = PropertyImage.objects.all()[:5]
    print(f"   Total de imágenes en la base de datos: {PropertyImage.objects.count()}")
    
    for i, imagen in enumerate(imagenes_directas):
        print(f"\n   Imagen {i+1}:")
        print(f"     ID: {imagen.id}")
        print(f"     property_id: {imagen.property_id}")
        print(f"     URL: {imagen.imagen}")
        print(f"     Orden: {imagen.orden}")
        
        # Verificar si la URL es accesible
        if imagen.imagen:
            import requests
            try:
                response = requests.head(imagen.imagen, timeout=3)
                print(f"     Status HTTP: {response.status_code}")
                if response.status_code == 200:
                    print(f"     [OK] Imagen accesible")
                else:
                    print(f"     [WARNING] Imagen no accesible (status: {response.status_code})")
            except Exception as e:
                print(f"     [ERROR] Error al acceder: {e}")
    
    # 7. Probar con una propiedad específica que debería tener imágenes
    print("\n4. Buscando propiedades con imágenes:")
    propiedades_con_imagenes = []
    for propiedad in PropifaiProperty.objects.all()[:10]:  # Revisar solo las primeras 10
        if propiedad.imagenes_relacionadas.exists():
            propiedades_con_imagenes.append(propiedad)
            if len(propiedades_con_imagenes) >= 3:
                break
    
    if propiedades_con_imagenes:
        print(f"   Encontradas {len(propiedades_con_imagenes)} propiedades con imágenes:")
        for propiedad in propiedades_con_imagenes:
            print(f"     - {propiedad.code}: {propiedad.imagenes_relacionadas.count()} imágenes")
            print(f"       URL principal: {propiedad.imagen_url}")
    else:
        print("   No se encontraron propiedades con imágenes en las primeras 10.")
        
        # Verificar si hay imágenes en la tabla property_images
        total_imagenes = PropertyImage.objects.count()
        print(f"   Total de registros en property_images: {total_imagenes}")
        
        if total_imagenes > 0:
            # Mostrar algunos property_id únicos
            from django.db import connections
            with connections['propifai'].cursor() as cursor:
                cursor.execute("SELECT DISTINCT TOP 5 property_id FROM property_images")
                property_ids = cursor.fetchall()
                print(f"   IDs de propiedades con imágenes: {[pid[0] for pid in property_ids]}")
                
                # Verificar si alguno de estos IDs existe en properties
                for pid in property_ids:
                    exists = PropifaiProperty.objects.filter(id=pid[0]).exists()
                    print(f"     Property ID {pid[0]}: {'EXISTE' if exists else 'NO EXISTE'} en properties")

if __name__ == '__main__':
    test_imagenes_implementation()