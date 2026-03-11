#!/usr/bin/env python
"""
Test directo para verificar propiedades de Propify.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

print("=== TEST DIRECTO DE PROPIEDADES PROPIFFY ===\n")

# 1. Verificar conexión directa a la base de datos Propifai
try:
    from propifai.models import PropifaiProperty
    print("1. Conexión a modelo PropifaiProperty:")
    count = PropifaiProperty.objects.using('propifai').count()
    print(f"   - Total propiedades en tabla: {count}")
    
    # Mostrar algunas propiedades
    propiedades = PropifaiProperty.objects.using('propifai').all()[:5]
    print(f"   - Primeras 5 propiedades:")
    for i, prop in enumerate(propiedades):
        print(f"     {i+1}. ID: {prop.id}, Código: {prop.code}, Departamento: {prop.department}")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n2. Test de vista ListaPropiedadesView:")

from django.test import RequestFactory
from ingestas.views import ListaPropiedadesView

factory = RequestFactory()

# Caso A: Todas las fuentes (sin parámetros)
print("\n   Caso A: Sin parámetros (debería mostrar todas)")
request = factory.get('/ingestas/propiedades/')
view = ListaPropiedadesView()
view.setup(request)
view.object_list = view.get_queryset()
context = view.get_context_data()

print(f"   - fuente_local_checked: {context.get('fuente_local_checked')}")
print(f"   - fuente_externa_checked: {context.get('fuente_externa_checked')}")
print(f"   - fuente_propify_checked: {context.get('fuente_propify_checked')}")
print(f"   - conteo_locales: {context.get('conteo_locales')}")
print(f"   - conteo_externas: {context.get('conteo_externas')}")
print(f"   - conteo_propify: {context.get('conteo_propify')}")
print(f"   - total_propiedades: {context.get('total_propiedades')}")

# Verificar propiedades de Propify en el resultado
todas_propiedades = context.get('todas_propiedades', [])
propiedades_propify = [p for p in todas_propiedades if p.get('es_propify')]
print(f"   - Propiedades con es_propify=True: {len(propiedades_propify)}")

if propiedades_propify:
    print(f"   - Ejemplo de propiedad Propify:")
    prop = propiedades_propify[0]
    print(f"     ID: {prop.get('id')}")
    print(f"     Tipo: {prop.get('tipo_propiedad')}")
    print(f"     Precio: {prop.get('precio_usd')}")
    print(f"     Departamento: {prop.get('departamento')}")
    print(f"     Fuente: {prop.get('fuente')}")

# Caso B: Solo Propify
print("\n   Caso B: Solo Propify (fuente_propify=propify)")
request2 = factory.get('/ingestas/propiedades/', {'fuente_propify': 'propify'})
view2 = ListaPropiedadesView()
view2.setup(request2)
view2.object_list = view2.get_queryset()
context2 = view2.get_context_data()

print(f"   - fuente_propify_checked: {context2.get('fuente_propify_checked')}")
print(f"   - conteo_propify: {context2.get('conteo_propify')}")
print(f"   - total_propiedades: {context2.get('total_propiedades')}")

# Verificar que solo hay propiedades de Propify
todas_propiedades2 = context2.get('todas_propiedades', [])
if todas_propiedades2:
    tipos_fuentes = set(p.get('fuente') for p in todas_propiedades2)
    print(f"   - Fuentes presentes: {tipos_fuentes}")

print("\n=== FIN DEL TEST ===")
print("\nCONCLUSION:")
if propiedades_propify:
    print(f"- Hay {len(propiedades_propify)} propiedades de Propify disponibles.")
    print("- El sistema está funcionando correctamente.")
else:
    print("- NO se encontraron propiedades de Propify en los resultados.")
    print("- Revisar la lógica de filtrado en la vista.")