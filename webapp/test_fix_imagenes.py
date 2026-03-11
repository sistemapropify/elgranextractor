#!/usr/bin/env python
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty
import requests

print("=== PRUEBA DE CORRECCIÓN DE IMÁGENES ===\n")

# Obtener algunas propiedades
props = PropifaiProperty.objects.all()[:5]
for p in props:
    print(f"Propiedad: {p.code} (ID: {p.id})")
    url = p.imagen_url
    print(f"  URL generada: {url}")
    
    if url:
        # Verificar si la URL es accesible
        try:
            r = requests.head(url, timeout=5)
            print(f"  Status HTTP: {r.status_code}")
            if r.status_code == 200:
                print("  ✓ Imagen accesible")
            else:
                print("  ✗ Imagen no accesible (status diferente de 200)")
        except Exception as e:
            print(f"  ✗ Error al acceder: {e}")
    else:
        print("  No hay URL de imagen")
    print()

print("=== FIN DE PRUEBA ===")