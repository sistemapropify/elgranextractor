#!/usr/bin/env python
"""
Test rapido para verificar propiedades de Propify.
"""
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

print("TEST RAPIDO - Propiedades de Propify")
print("=====================================\n")

# 1. Verificar base de datos directamente
from propifai.models import PropifaiProperty
count = PropifaiProperty.objects.using('propifai').count()
print(f"1. Propiedades en tabla Propifai: {count}")

if count > 0:
    # Obtener una propiedad de ejemplo
    prop = PropifaiProperty.objects.using('propifai').first()
    print(f"   Ejemplo - ID: {prop.id}, Codigo: {prop.code}")
    print(f"   Departamento: {prop.department}, Provincia: {prop.province}")
    print(f"   Precio: {prop.price}, Habitaciones: {prop.bedrooms}")
    print(f"   Latitude: {prop.latitude}, Longitude: {prop.longitude}")

# 2. Verificar vista
from django.test import RequestFactory
from ingestas.views import ListaPropiedadesView

factory = RequestFactory()
request = factory.get('/ingestas/propiedades/', {'fuente_propify': 'propify'})

view = ListaPropiedadesView()
view.setup(request)
view.object_list = view.get_queryset()

try:
    context = view.get_context_data()
    print(f"\n2. Vista - fuente_propify_checked: {context.get('fuente_propify_checked')}")
    print(f"   Conteo propify: {context.get('conteo_propify')}")
    print(f"   Total propiedades: {context.get('total_propiedades')}")
    
    # Verificar propiedades de Propify
    todas = context.get('todas_propiedades', [])
    propify_props = [p for p in todas if p.get('es_propify')]
    print(f"   Propiedades con es_propify=True: {len(propify_props)}")
    
    if propify_props:
        print(f"\n3. Primeras 3 propiedades de Propify en resultados:")
        for i, p in enumerate(propify_props[:3]):
            print(f"   {i+1}. ID: {p.get('id')}, Tipo: {p.get('tipo_propiedad')}")
            print(f"      Precio: {p.get('precio_usd')}, Depto: {p.get('departamento')}")
            print(f"      Fuente: {p.get('fuente')}, Es externo: {p.get('es_externo')}")
    else:
        print("\n3. ERROR: No hay propiedades de Propify en los resultados!")
        
        # Verificar si hay error en la conversion
        print("\n   Debug - Verificando conversion:")
        from ingestas.views import ListaPropiedadesView
        view_obj = ListaPropiedadesView()
        
        # Obtener una propiedad de Propifai y convertirla
        if count > 0:
            propifai_prop = PropifaiProperty.objects.using('propifai').first()
            converted = view_obj._convertir_propiedad_propifai_a_dict(propifai_prop)
            print(f"   Propiedad convertida: {converted.keys()}")
            print(f"   Tiene es_propify: {converted.get('es_propify')}")
            print(f"   Tiene fuente: {converted.get('fuente')}")
            
except Exception as e:
    print(f"ERROR en vista: {e}")
    import traceback
    traceback.print_exc()

print("\n=====================================")
if count > 0 and propify_props:
    print("RESULTADO: Las propiedades de Propify estan disponibles en el sistema.")
    print(f"Se encontraron {len(propify_props)} propiedades de Propify.")
else:
    print("RESULTADO: Hay un problema - las propiedades de Propify no se estan mostrando.")