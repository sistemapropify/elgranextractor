#!/usr/bin/env python
"""
Test después del cambio en la lógica de checkboxes.
"""
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from ingestas.views import ListaPropiedadesView

print("=== TEST DESPUES DEL CAMBIO ===\n")

factory = RequestFactory()

# Caso A: Solo Propify marcado
print("Caso A: Solo fuente_propify=propify")
request = factory.get('/ingestas/propiedades/', {'fuente_propify': 'propify'})
view = ListaPropiedadesView()
view.setup(request)
view.object_list = view.get_queryset()
context = view.get_context_data()

print(f"  fuente_local_checked: {context.get('fuente_local_checked')}")
print(f"  fuente_externa_checked: {context.get('fuente_externa_checked')}")
print(f"  fuente_propify_checked: {context.get('fuente_propify_checked')}")
print(f"  conteo_propify: {context.get('conteo_propify')}")
print(f"  total_propiedades: {context.get('total_propiedades')}")

# Caso B: Con otros parámetros pero sin checkboxes
print("\nCaso B: Con otros filtros (departamento) pero sin checkboxes")
request2 = factory.get('/ingestas/propiedades/', {'departamento': 'Lima'})
view2 = ListaPropiedadesView()
view2.setup(request2)
view2.object_list = view2.get_queryset()
context2 = view2.get_context_data()

print(f"  fuente_local_checked: {context2.get('fuente_local_checked')}")
print(f"  fuente_externa_checked: {context2.get('fuente_externa_checked')}")
print(f"  fuente_propify_checked: {context2.get('fuente_propify_checked')}")

# Caso C: Sin parámetros (primera carga)
print("\nCaso C: Sin parámetros (primera carga)")
request3 = factory.get('/ingestas/propiedades/')
view3 = ListaPropiedadesView()
view3.setup(request3)
view3.object_list = view3.get_queryset()
context3 = view3.get_context_data()

print(f"  fuente_local_checked: {context3.get('fuente_local_checked')}")
print(f"  fuente_externa_checked: {context3.get('fuente_externa_checked')}")
print(f"  fuente_propify_checked: {context3.get('fuente_propify_checked')}")
print(f"  conteo_propify: {context3.get('conteo_propify')}")

# Verificar si hay propiedades de Propify
if context3.get('conteo_propify', 0) == 0:
    print("\n¡ALERTA! conteo_propify es 0. Verificando conexión a base de datos...")
    
    try:
        from propifai.models import PropifaiProperty
        count = PropifaiProperty.objects.using('propifai').count()
        print(f"  Propiedades en tabla Propifai: {count}")
        
        if count == 0:
            print("  ¡La tabla Propifai está vacía!")
        else:
            print("  ¡La tabla tiene datos pero no se están mostrando!")
            
            # Verificar si hay excepciones silenciosas
            print("  Probando obtener propiedades directamente...")
            try:
                props = list(PropifaiProperty.objects.using('propifai').all()[:5])
                print(f"  Se obtuvieron {len(props)} propiedades de ejemplo")
            except Exception as e:
                print(f"  ERROR al obtener propiedades: {e}")
                
    except Exception as e:
        print(f"  ERROR al importar modelo: {e}")

print("\n=== FIN DEL TEST ===")