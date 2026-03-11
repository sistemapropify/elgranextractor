#!/usr/bin/env python
"""
Verificación del template para propiedades Propify.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from django.template import loader, Context

# Crear un request con solo Propify marcado
factory = RequestFactory()
request = factory.get('/ingestas/propiedades/', data={'fuente_propify': 'propify'})

# Obtener la vista y llamar al método get()
from ingestas.views import ListaPropiedadesView
view = ListaPropiedadesView()
view.setup(request)

# Llamar al método get() para ejecutar la lógica completa
response = view.get(request)
context = view.get_context_data()

print("=== VERIFICACIÓN DEL TEMPLATE ===\n")

# 1. Verificar variables en el contexto
print("1. Variables en el contexto:")
print(f"   - total_propiedades: {context.get('total_propiedades')}")
print(f"   - conteo_locales: {context.get('conteo_locales')}")
print(f"   - conteo_externas: {context.get('conteo_externas')}")
print(f"   - conteo_propify: {context.get('conteo_propify')}")
print(f"   - fuente_local_checked: {context.get('fuente_local_checked')}")
print(f"   - fuente_externa_checked: {context.get('fuente_externa_checked')}")
print(f"   - fuente_propify_checked: {context.get('fuente_propify_checked')}")
print(f"   - todas_propiedades (cantidad): {len(context.get('todas_propiedades', []))}")

# 2. Verificar propiedades Propify en el contexto
print("\n2. Propiedades Propify en el contexto:")
propify_props = [p for p in context.get('todas_propiedades', []) if p.get('es_propify')]
print(f"   - Cantidad de propiedades Propify: {len(propify_props)}")

if propify_props:
    print(f"   - Primera propiedad Propify:")
    prop = propify_props[0]
    print(f"     * ID: {prop.get('id')}")
    print(f"     * Código: {prop.get('codigo')}")
    print(f"     * Departamento: {prop.get('departamento')}")
    print(f"     * Latitud: {prop.get('lat')}")
    print(f"     * Longitud: {prop.get('lng')}")
    print(f"     * Tiene es_propify=True: {prop.get('es_propify')}")
    print(f"     * Tiene es_externo=True: {prop.get('es_externo')}")

# 3. Renderizar el template manualmente
print("\n3. Renderizando template...")
try:
    template = loader.get_template('ingestas/lista_propiedades_rediseno.html')
    html_content = template.render(context, request)
    
    # Buscar elementos en el HTML
    print(f"   - HTML generado: {len(html_content)} caracteres")
    
    # Buscar checkboxes
    checkbox_local = 'id="filter-fuente-local"' in html_content
    checkbox_externa = 'id="filter-fuente-externa"' in html_content
    checkbox_propify = 'id="filter-fuente-propify"' in html_content
    
    print(f"   - Checkbox Local en HTML: {'Sí' if checkbox_local else 'No'}")
    print(f"   - Checkbox Externa en HTML: {'Sí' if checkbox_externa else 'No'}")
    print(f"   - Checkbox Propify en HTML: {'Sí' if checkbox_propify else 'No'}")
    
    # Verificar si el checkbox Propify está checked
    if checkbox_propify:
        propify_index = html_content.find('id="filter-fuente-propify"')
        snippet = html_content[propify_index:propify_index+200]
        is_checked = 'checked' in snippet
        print(f"   - Checkbox Propify checked: {'Sí' if is_checked else 'No'}")
        print(f"   - Snippet: {snippet[:100]}...")
    
    # Buscar propiedades Propify en el HTML
    propify_count_html = html_content.count('data-es-propify="true"')
    print(f"   - Propiedades Propify en HTML (data-es-propify): {propify_count_html}")
    
    # Buscar tarjetas de propiedades
    card_count = html_content.count('class="property-card"')
    print(f"   - Total tarjetas de propiedades: {card_count}")
    
    # Buscar badges "Propify"
    badge_propify_count = html_content.count('badge bg-success text-white ms-1')
    print(f"   - Badges 'Propify' en HTML: {badge_propify_count}")
    
    # Buscar coordenadas en el HTML
    lat_count = html_content.count('data-lat=')
    lng_count = html_content.count('data-lng=')
    print(f"   - Atributos data-lat: {lat_count}")
    print(f"   - Atributos data-lng: {lng_count}")
    
    # Extraer un fragmento del HTML para inspección
    if 'data-es-propify="true"' in html_content:
        propify_index = html_content.find('data-es-propify="true"')
        start = max(0, propify_index - 500)
        end = min(len(html_content), propify_index + 500)
        print(f"\n   - Fragmento HTML alrededor de data-es-propify:")
        print(f"     {html_content[start:end]}")
    
except Exception as e:
    print(f"ERROR renderizando template: {e}")
    import traceback
    traceback.print_exc()

# 4. Verificar el JavaScript del mapa
print("\n4. Verificando JavaScript del mapa...")
try:
    # Buscar la función addMarker en el HTML
    if 'html_content' in locals():
        if 'function addMarker' in html_content:
            print("   - Función addMarker encontrada en HTML")
            
            # Buscar el icono verde para Propify
            if 'green-dot.png' in html_content:
                print("   - Icono green-dot.png encontrado (para Propify)")
            else:
                print("   - Icono green-dot.png NO encontrado")
                
            # Buscar el manejo de esPropify
            if 'esPropify' in html_content:
                print("   - Variable esPropify encontrada en JavaScript")
            else:
                print("   - Variable esPropify NO encontrada en JavaScript")
except:
    pass