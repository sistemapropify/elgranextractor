#!/usr/bin/env python
"""
Test específico para la conversión de propiedades Propifai.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty
from ingestas.views import ListaPropiedadesView

print("=== TEST DE CONVERSION PROPY ===")
print()

# Obtener algunas propiedades
props = list(PropifaiProperty.objects.using('propifai')[:3])

if not props:
    print("ERROR: No hay propiedades en la base de datos Propifai")
    sys.exit(1)

# Crear instancia de la vista
view = ListaPropiedadesView()

print(f"Propiedades obtenidas: {len(props)}")
print()

for i, prop in enumerate(props):
    print(f"--- Propiedad {i+1} (ID={prop.id}) ---")
    
    # Mostrar campos relevantes
    print(f"  Campos directos:")
    print(f"    - code: {prop.code}")
    print(f"    - department: {prop.department} (tipo: {type(prop.department)})")
    print(f"    - province: {prop.province}")
    print(f"    - district: {prop.district}")
    print(f"    - coordinates: {prop.coordinates}")
    print(f"    - price: {prop.price}")
    print(f"    - bedrooms: {prop.bedrooms}")
    print(f"    - bathrooms: {prop.bathrooms}")
    print(f"    - built_area: {prop.built_area}")
    print(f"    - land_area: {prop.land_area}")
    
    # Mostrar propiedades computadas
    print(f"  Propiedades computadas:")
    print(f"    - latitude: {prop.latitude}")
    print(f"    - longitude: {prop.longitude}")
    print(f"    - tipo_propiedad: {prop.tipo_propiedad}")
    print(f"    - precio_formateado: {prop.precio_formateado}")
    
    # Intentar convertir a diccionario
    try:
        prop_dict = view._convertir_propiedad_propifai_a_dict(prop)
        print(f"  Diccionario convertido:")
        print(f"    - id: {prop_dict.get('id')}")
        print(f"    - es_propify: {prop_dict.get('es_propify')}")
        print(f"    - tipo_propiedad: {prop_dict.get('tipo_propiedad')}")
        print(f"    - departamento: {prop_dict.get('departamento')}")
        print(f"    - precio_usd: {prop_dict.get('precio_usd')}")
        print(f"    - lat: {prop_dict.get('lat')}")
        print(f"    - lng: {prop_dict.get('lng')}")
    except Exception as e:
        print(f"  ERROR en conversion: {e}")
        import traceback
        traceback.print_exc()
    
    print()

# Testear la función get_context_data con un request simulado
print("=== TEST DE VISTA COMPLETA ===")
print()

try:
    from django.test import RequestFactory
    
    # Crear una solicitud GET con filtro solo Propify
    factory = RequestFactory()
    request = factory.get('/ingestas/propiedades/?fuente_propify=propify')
    
    # Crear instancia de la vista y llamar a get() primero
    view = ListaPropiedadesView()
    view.setup(request)
    response = view.get(request)
    
    # Obtener contexto de la respuesta
    if hasattr(response, 'context_data'):
        context = response.context_data
        print(f"Contexto obtenido de la vista:")
        print(f"  - conteo_locales: {context.get('conteo_locales', 0)}")
        print(f"  - conteo_externas: {context.get('conteo_externas', 0)}")
        print(f"  - conteo_propify: {context.get('conteo_propify', 0)}")
        print(f"  - total_propiedades: {context.get('total_propiedades', 0)}")
        print(f"  - fuente_propify_checked: {context.get('fuente_propify_checked', False)}")
        
        # Verificar propiedades Propify
        todas_propiedades = context.get('todas_propiedades', [])
        propify_props = [p for p in todas_propiedades if p.get('es_propify')]
        print(f"  - Propiedades Propify en todas_propiedades: {len(propify_props)}")
        
        if propify_props:
            print(f"  - Ejemplo de propiedad Propify:")
            print(f"    ID: {propify_props[0].get('id')}")
            print(f"    Tipo: {propify_props[0].get('tipo_propiedad')}")
            print(f"    Departamento: {propify_props[0].get('departamento')}")
            print(f"    Precio: {propify_props[0].get('precio_usd')}")
    else:
        print("ERROR: No se pudo obtener contexto de la respuesta")
        
except Exception as e:
    print(f"ERROR en test de vista: {e}")
    import traceback
    traceback.print_exc()

print()
print("=== FIN DEL TEST ===")