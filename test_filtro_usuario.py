#!/usr/bin/env python
"""
Simular exactamente lo que el usuario está haciendo: filtrar solo Propify.
"""
import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from ingestas.views import ListaPropiedadesView

print("=== SIMULACION DE FILTRO SOLO PROPIFFY ===\n")

factory = RequestFactory()

# Caso 1: Solo checkbox Propify marcado (otros desmarcados)
print("1. Solicitud con solo fuente_propify=propify:")
print("   (simula usuario marcando solo checkbox Propify)")
request = factory.get('/ingestas/propiedades/', {'fuente_propify': 'propify'})

view = ListaPropiedadesView()
view.setup(request)
view.object_list = view.get_queryset()
context = view.get_context_data()

print(f"   fuente_local en GET: {'fuente_local' in request.GET}")
print(f"   fuente_externa en GET: {'fuente_externa' in request.GET}")
print(f"   fuente_propify en GET: {'fuente_propify' in request.GET}")
print(f"   fuente_local_checked: {context.get('fuente_local_checked')}")
print(f"   fuente_externa_checked: {context.get('fuente_externa_checked')}")
print(f"   fuente_propify_checked: {context.get('fuente_propify_checked')}")
print(f"   conteo_locales: {context.get('conteo_locales')}")
print(f"   conteo_externas: {context.get('conteo_externas')}")
print(f"   conteo_propify: {context.get('conteo_propify')}")
print(f"   total_propiedades: {context.get('total_propiedades')}")

# Verificar qué propiedades se están incluyendo
todas = context.get('todas_propiedades', [])
if todas:
    fuentes_presentes = set(p.get('fuente') for p in todas)
    print(f"   Fuentes presentes en resultados: {fuentes_presentes}")
    
    # Contar por fuente
    locales = [p for p in todas if p.get('fuente') == 'Local' or p.get('fuente') == 'Local DB']
    externas = [p for p in todas if p.get('fuente') == 'Externa' or 'Externa' in str(p.get('fuente'))]
    propify = [p for p in todas if p.get('fuente') == 'Propify DB' or p.get('es_propify')]
    
    print(f"   Propiedades locales en resultados: {len(locales)}")
    print(f"   Propiedades externas en resultados: {len(externas)}")
    print(f"   Propiedades Propify en resultados: {len(propify)}")
    
    if len(locales) > 0 and context.get('fuente_local_checked') == False:
        print("   ¡PROBLEMA! Hay propiedades locales aunque fuente_local_checked es False")
    if len(externas) > 0 and context.get('fuente_externa_checked') == False:
        print("   ¡PROBLEMA! Hay propiedades externas aunque fuente_externa_checked es False")

# Caso 2: Verificar qué pasa cuando NO hay parámetros GET (primera carga)
print("\n2. Solicitud sin parámetros (primera carga):")
request2 = factory.get('/ingestas/propiedades/')
view2 = ListaPropiedadesView()
view2.setup(request2)
view2.object_list = view2.get_queryset()
context2 = view2.get_context_data()

print(f"   request.GET vacío: {len(request2.GET) == 0}")
print(f"   fuente_local_checked: {context2.get('fuente_local_checked')}")
print(f"   fuente_externa_checked: {context2.get('fuente_externa_checked')}")
print(f"   fuente_propify_checked: {context2.get('fuente_propify_checked')}")
print(f"   conteo_propify: {context2.get('conteo_propify')}")

print("\n=== DIAGNOSTICO ===")
if context.get('conteo_propify') == 0:
    print("PROBLEMA: conteo_propify es 0 aunque debería ser 42")
    print("Posibles causas:")
    print("1. Error al conectar con la base de datos Propifai")
    print("2. El modelo PropifaiProperty no está accesible")
    print("3. Hay un exception silencioso en la vista")
else:
    print("OK: conteo_propify es mayor que 0")
    
if context.get('fuente_local_checked') == True and len(request.GET) == 1:
    print("PROBLEMA: fuente_local_checked es True aunque solo se envió fuente_propify")
    print("Esto haría que se muestren propiedades locales cuando no deberían")