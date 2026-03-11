#!/usr/bin/env python
"""
Script simple para depurar el problema de Propify.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty

print("=== DEPURACION DE PROPIEDADES PROPY ===")
print()

# 1. Verificar conexión directa a la base de datos Propifai
print("1. Verificando conexion directa a la base de datos Propifai...")
try:
    # Usando using('propifai') explícitamente
    count = PropifaiProperty.objects.using('propifai').count()
    print(f"   OK - Conteo usando using('propifai'): {count} propiedades")
    
    # Usando all() sin using (debería usar el router)
    count_all = PropifaiProperty.objects.all().count()
    print(f"   OK - Conteo usando objects.all(): {count_all} propiedades")
    
    # Obtener algunas propiedades
    props = list(PropifaiProperty.objects.using('propifai')[:5])
    print(f"   OK - Primeras 5 propiedades obtenidas: {len(props)}")
    for i, prop in enumerate(props):
        print(f"     Propiedad {i+1}: ID={prop.id}, Codigo={prop.code}, Departamento={prop.department}")
        
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print()

# 2. Verificar si el modelo tiene datos
print("2. Verificando estructura del modelo...")
try:
    # Verificar campos del modelo
    fields = [f.name for f in PropifaiProperty._meta.fields]
    print(f"   OK - Campos del modelo: {len(fields)} campos")
    print(f"   OK - Primeros 10 campos: {fields[:10]}")
    
    # Verificar si hay datos
    if count > 0:
        first = PropifaiProperty.objects.using('propifai').first()
        print(f"   OK - Primera propiedad: ID={first.id}, Code={first.code}")
        print(f"   OK - Coordenadas: {first.coordinates}")
        print(f"   OK - Latitude property: {first.latitude}")
        print(f"   OK - Longitude property: {first.longitude}")
    else:
        print("   WARNING - No hay propiedades en la base de datos Propifai")
        
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print()

# 3. Verificar la vista directamente
print("3. Verificando la vista ListaPropiedadesView...")
try:
    from ingestas.views import ListaPropiedadesView
    from django.test import RequestFactory
    
    # Crear una solicitud GET con filtro solo Propify
    factory = RequestFactory()
    request = factory.get('/ingestas/propiedades/?fuente_propify=propify')
    
    # Crear instancia de la vista
    view = ListaPropiedadesView()
    view.request = request
    
    # Obtener contexto
    context = view.get_context_data()
    
    print(f"   OK - Conteo locales: {context.get('conteo_locales', 0)}")
    print(f"   OK - Conteo externas: {context.get('conteo_externas', 0)}")
    print(f"   OK - Conteo propify: {context.get('conteo_propify', 0)}")
    print(f"   OK - Total propiedades: {context.get('total_propiedades', 0)}")
    print(f"   OK - fuente_propify_checked: {context.get('fuente_propify_checked', False)}")
    
    # Verificar propiedades_propifai_dict
    todas_propiedades = context.get('todas_propiedades', [])
    propify_props = [p for p in todas_propiedades if p.get('es_propify')]
    print(f"   OK - Propiedades Propify en todas_propiedades: {len(propify_props)}")
    
    if propify_props:
        print(f"   OK - Ejemplo de propiedad Propify: ID={propify_props[0].get('id')}, Tipo={propify_props[0].get('tipo_propiedad')}")
    else:
        print("   WARNING - No hay propiedades Propify en todas_propiedades")
    
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
print("=== FIN DE DEPURACION ===")