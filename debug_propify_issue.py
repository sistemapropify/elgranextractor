#!/usr/bin/env python
"""
Script para depurar el problema de Propify en la vista ListaPropiedadesView.
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
from django.test import RequestFactory

print("=== DEPURACIÓN DE PROPIEDADES PROPY ===")
print()

# 1. Verificar conexión directa a la base de datos Propifai
print("1. Verificando conexión directa a la base de datos Propifai...")
try:
    # Usando using('propifai') explícitamente
    count = PropifaiProperty.objects.using('propifai').count()
    print(f"   ✓ Conteo usando using('propifai'): {count} propiedades")
    
    # Usando all() sin using (debería usar el router)
    count_all = PropifaiProperty.objects.all().count()
    print(f"   ✓ Conteo usando objects.all(): {count_all} propiedades")
    
    # Obtener algunas propiedades
    props = list(PropifaiProperty.objects.using('propifai')[:5])
    print(f"   ✓ Primeras 5 propiedades obtenidas: {len(props)}")
    for i, prop in enumerate(props):
        print(f"     Propiedad {i+1}: ID={prop.id}, Código={prop.code}, Departamento={prop.department}")
        
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# 2. Simular la vista ListaPropiedadesView
print("2. Simulando la vista ListaPropiedadesView...")
try:
    # Crear una solicitud GET con filtro solo Propify
    factory = RequestFactory()
    request = factory.get('/ingestas/propiedades/?fuente_propify=propify')
    
    # Crear instancia de la vista
    view = ListaPropiedadesView()
    view.request = request
    
    # Obtener contexto
    context = view.get_context_data()
    
    print(f"   ✓ Conteo locales en contexto: {context.get('conteo_locales', 0)}")
    print(f"   ✓ Conteo externas en contexto: {context.get('conteo_externas', 0)}")
    print(f"   ✓ Conteo propify en contexto: {context.get('conteo_propify', 0)}")
    print(f"   ✓ Total propiedades en contexto: {context.get('total_propiedades', 0)}")
    
    # Verificar si fuente_propify está configurado correctamente
    print(f"   ✓ fuente_propify_checked: {context.get('fuente_propify_checked', False)}")
    
    # Verificar propiedades_propifai_dict
    todas_propiedades = context.get('todas_propiedades', [])
    propify_props = [p for p in todas_propiedades if p.get('es_propify')]
    print(f"   ✓ Propiedades Propify en todas_propiedades: {len(propify_props)}")
    
    if propify_props:
        print(f"   ✓ Ejemplo de propiedad Propify: ID={propify_props[0].get('id')}, Tipo={propify_props[0].get('tipo_propiedad')}")
    
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# 3. Verificar el código específico de la vista
print("3. Verificando el código de get_context_data()...")
try:
    # Importar la función de conversión
    view = ListaPropiedadesView()
    
    # Simular la obtención de propiedades de Propifai
    from propifai.models import PropifaiProperty
    propiedades_propifai = list(PropifaiProperty.objects.all()[:100])
    print(f"   ✓ propiedades_propifai obtenidas: {len(propiedades_propifai)}")
    
    # Convertir a diccionarios
    propiedades_propifai_dict = [view._convertir_propiedad_propifai_a_dict(prop) for prop in propiedades_propifai]
    print(f"   ✓ propiedades_propifai_dict convertidas: {len(propiedades_propifai_dict)}")
    
    if propiedades_propifai_dict:
        print(f"   ✓ Ejemplo de diccionario: {propiedades_propifai_dict[0].get('id')}, {propiedades_propifai_dict[0].get('tipo_propiedad')}")
    
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# 4. Verificar configuración de routers
print("4. Verificando configuración de routers...")
try:
    from django.db import connections
    from webapp.routers import PropifaiRouter
    
    router = PropifaiRouter()
    
    # Verificar qué base de datos usaría para PropifaiProperty
    from propifai.models import PropifaiProperty
    db_for_read = router.db_for_read(PropifaiProperty)
    print(f"   ✓ Router.db_for_read(PropifaiProperty): {db_for_read}")
    
    # Verificar conexiones
    print(f"   ✓ Conexiones disponibles: {list(connections.databases.keys())}")
    
    # Verificar si la conexión propifai está configurada
    if 'propifai' in connections.databases:
        print(f"   ✓ Conexión 'propifai' configurada en settings")
    else:
        print(f"   ✗ Conexión 'propifai' NO configurada en settings")
        
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=== FIN DE DEPURACIÓN ===")