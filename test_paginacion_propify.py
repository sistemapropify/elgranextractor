#!/usr/bin/env python
"""
Test para verificar que las propiedades Propify aparecen en la primera página.
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

print("=== TEST DE PAGINACIÓN PARA PROPIFY ===\n")

factory = RequestFactory()

# Test 1: Solo Propify marcado, primera página
print("Test 1: Solo Propify marcado (primera página)")
request = factory.get('/ingestas/propiedades/', data={'fuente_propify': 'propify'})
view = ListaPropiedadesView()
view.setup(request)

# Llamar a paginate_queryset
paginator, page, object_list, is_paginated = view.paginate_queryset(None, 12)

print(f"   - Total propiedades: {paginator.count}")
print(f"   - Número de páginas: {paginator.num_pages}")
print(f"   - Página actual: {page.number}")
print(f"   - Propiedades en esta página: {len(object_list)}")

# Contar Propify en esta página
propify_en_pagina = sum(1 for p in object_list if p.get('es_propify'))
print(f"   - Propiedades Propify en esta página: {propify_en_pagina}")

if propify_en_pagina > 0:
    print(f"   - ✓ Hay propiedades Propify en la primera página")
    # Mostrar detalles de las primeras propiedades Propify
    print(f"   - Primeras propiedades Propify en la página:")
    for i, prop in enumerate([p for p in object_list if p.get('es_propify')][:3], 1):
        print(f"     {i}. ID: {prop.get('id')}, Código: {prop.get('codigo')}")
        print(f"        Coordenadas: Lat={prop.get('lat')}, Lng={prop.get('lng')}")
else:
    print(f"   - ✗ NO hay propiedades Propify en la primera página")
    print(f"   - Esto explica por qué el usuario no las ve")

# Test 2: Todas las fuentes, primera página
print("\nTest 2: Todas las fuentes (primera página)")
request = factory.get('/ingestas/propiedades/', data={})
view = ListaPropiedadesView()
view.setup(request)

paginator, page, object_list, is_paginated = view.paginate_queryset(None, 12)

print(f"   - Total propiedades: {paginator.count}")
print(f"   - Propiedades en esta página: {len(object_list)}")

# Contar por tipo en esta página
locales_en_pagina = sum(1 for p in object_list if not p.get('es_externo') and not p.get('es_propify'))
externas_en_pagina = sum(1 for p in object_list if p.get('es_externo') and not p.get('es_propify'))
propify_en_pagina = sum(1 for p in object_list if p.get('es_propify'))

print(f"   - Locales en página: {locales_en_pagina}")
print(f"   - Externas en página: {externas_en_pagina}")
print(f"   - Propify en página: {propify_en_pagina}")

if propify_en_pagina > 0:
    print(f"   - ✓ Hay propiedades Propify en la primera página con todas las fuentes")
else:
    print(f"   - ✗ NO hay propiedades Propify en la primera página con todas las fuentes")
    print(f"   - Esto podría deberse a que hay muchas propiedades locales (857) y pocas Propify (43)")
    print(f"   - Con la paginación de 12 propiedades por página, es probable que no aparezcan Propify hasta páginas posteriores")

# Test 3: Verificar todas las páginas para Propify
print("\nTest 3: Verificar distribución de Propify en todas las páginas (solo Propify)")
request = factory.get('/ingestas/propiedades/', data={'fuente_propify': 'propify'})
view = ListaPropiedadesView()
view.setup(request)

paginator, page, object_list, is_paginated = view.paginate_queryset(None, 12)

print(f"   - Total páginas: {paginator.num_pages}")
print(f"   - Propiedades por página: 12")

for page_num in range(1, paginator.num_pages + 1):
    page_obj = paginator.page(page_num)
    propify_count = sum(1 for p in page_obj.object_list if p.get('es_propify'))
    print(f"   - Página {page_num}: {len(page_obj.object_list)} propiedades, {propify_count} Propify")