#!/usr/bin/env python
"""
Debug específico para la lógica de checkboxes.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from ingestas.views import ListaPropiedadesView

print("=== DEBUG CHECKBOXES ===")
print()

# Simular diferentes escenarios
test_cases = [
    ("Sin parámetros (por defecto)", "/ingestas/propiedades/"),
    ("Solo Propify", "/ingestas/propiedades/?fuente_propify=propify"),
    ("Solo Externa", "/ingestas/propiedades/?fuente_externa=externa"),
    ("Solo Local", "/ingestas/propiedades/?fuente_local=local"),
    ("Propify y Externa", "/ingestas/propiedades/?fuente_propify=propify&fuente_externa=externa"),
    ("Todos explícitos", "/ingestas/propiedades/?fuente_local=local&fuente_externa=externa&fuente_propify=propify"),
]

factory = RequestFactory()

for test_name, url in test_cases:
    print(f"\n{test_name}:")
    print(f"  URL: {url}")
    
    request = factory.get(url)
    view = ListaPropiedadesView()
    view.request = request
    
    # Llamar a _obtener_todas_propiedades para ver qué propiedades obtiene
    todas_propiedades = view._obtener_todas_propiedades()
    
    # Calcular conteos manualmente
    conteo_locales = sum(1 for p in todas_propiedades if not p.get('es_externo') and not p.get('es_propify'))
    conteo_externas = sum(1 for p in todas_propiedades if p.get('es_externo') and not p.get('es_propify'))
    conteo_propify = sum(1 for p in todas_propiedades if p.get('es_propify'))
    
    print(f"  Propiedades obtenidas: {len(todas_propiedades)}")
    print(f"  Conteo locales: {conteo_locales}")
    print(f"  Conteo externas: {conteo_externas}")
    print(f"  Conteo propify: {conteo_propify}")
    
    # Verificar lógica de checkboxes en get_context_data
    # Simular la lógica de get_context_data
    has_any_checkbox_param = any(
        key in request.GET
        for key in ['fuente_local', 'fuente_externa', 'fuente_propify']
    )
    
    print(f"  has_any_checkbox_param: {has_any_checkbox_param}")
    
    if not has_any_checkbox_param:
        fuente_local = True
        fuente_externa = True
        fuente_propify = True
    else:
        fuente_local = 'fuente_local' in request.GET
        fuente_externa = 'fuente_externa' in request.GET
        fuente_propify = 'fuente_propify' in request.GET
    
    print(f"  fuente_local: {fuente_local}")
    print(f"  fuente_externa: {fuente_externa}")
    print(f"  fuente_propify: {fuente_propify}")
    
    # Verificar consistencia
    if fuente_local and conteo_locales == 0:
        print(f"  ⚠️  ADVERTENCIA: fuente_local=True pero conteo_locales=0")
    if fuente_externa and conteo_externas == 0:
        print(f"  ⚠️  ADVERTENCIA: fuente_externa=True pero conteo_externas=0")
    if fuente_propify and conteo_propify == 0:
        print(f"  ⚠️  ADVERTENCIA: fuente_propify=True pero conteo_propify=0")

print()
print("=== FIN DEBUG ===")