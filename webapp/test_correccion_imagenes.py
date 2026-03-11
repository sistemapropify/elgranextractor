#!/usr/bin/env python
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty
from propifai.views import ListaPropiedadesPropifyView
from django.test import RequestFactory

print("=== PRUEBA DE CORRECCIÓN DE IMÁGENES EN VISTA ===\n")

# Crear una solicitud simulada
factory = RequestFactory()
request = factory.get('/propifai/propiedades/')
view = ListaPropiedadesPropifyView()
view.request = request

# Obtener el contexto
context = view.get_context_data()

# Verificar algunas propiedades
propiedades = context['propiedades']
print(f"Número de propiedades en contexto: {len(propiedades)}")
if propiedades:
    for i, prop in enumerate(propiedades[:3]):
        print(f"\nPropiedad {i+1}:")
        print(f"  Código: {prop.get('codigo')}")
        print(f"  imagen_url: {prop.get('imagen_url')}")
        print(f"  primera_imagen: {prop.get('primera_imagen')}")
        print(f"  imagen_principal: {prop.get('imagen_principal')}")
        # Verificar si la URL es válida
        url = prop.get('imagen_url')
        if url:
            import requests
            try:
                r = requests.head(url, timeout=5)
                print(f"  Status HTTP: {r.status_code}")
            except Exception as e:
                print(f"  Error al acceder: {e}")
        else:
            print("  No hay URL de imagen")

print("\n=== FIN DE PRUEBA ===")