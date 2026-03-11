#!/usr/bin/env python3
"""
Verificación directa del contexto de la vista
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from ingestas.views import ListaPropiedadesView
from django.template import Template, Context
import json

def verificar_contexto_filtro_propify():
    """Verificar el contexto cuando se filtra solo por Propify"""
    print("=== VERIFICACIÓN DEL CONTEXTO CON FILTRO PROPIY ===")
    
    # Crear una request simulada
    factory = RequestFactory()
    request = factory.get('/ingestas/propiedades/', {'fuente_propify': 'propify'})
    request.user = None  # Para simplificar
    
    # Crear la vista
    view = ListaPropiedadesView()
    view.request = request
    view.kwargs = {}
    
    # Obtener el contexto
    context = view.get_context_data()
    
    print("\n--- CONTEXTO COMPLETO ---")
    for key, value in context.items():
        if key == 'paginator' or key == 'page_obj':
            print(f"{key}: {type(value)}")
        elif key == 'object_list':
            print(f"{key}: {len(value)} elementos")
            # Mostrar primeros 3 elementos
            for i, prop in enumerate(value[:3]):
                print(f"  Elemento {i}:")
                print(f"    Tipo: {type(prop)}")
                if isinstance(prop, dict):
                    print(f"    Keys: {list(prop.keys())}")
                    print(f"    es_propify: {prop.get('es_propify', 'NO EXISTE')}")
                    print(f"    es_externo: {prop.get('es_externo', 'NO EXISTE')}")
                    print(f"    id: {prop.get('id', prop.get('id_externo', 'NO EXISTE'))}")
                else:
                    print(f"    Objeto: {prop}")
        elif isinstance(value, (list, tuple)):
            print(f"{key}: {len(value)} elementos")
        else:
            print(f"{key}: {value}")
    
    # Verificar las propiedades específicamente
    print("\n--- ANÁLISIS DE PROPIEDADES ---")
    object_list = context.get('object_list', [])
    print(f"Total de propiedades en object_list: {len(object_list)}")
    
    # Contar por tipo
    propify_count = 0
    externo_count = 0
    local_count = 0
    
    for prop in object_list:
        if isinstance(prop, dict):
            if prop.get('es_propify'):
                propify_count += 1
            elif prop.get('es_externo'):
                externo_count += 1
            else:
                local_count += 1
    
    print(f"Propiedades Propify: {propify_count}")
    print(f"Propiedades Externas: {externo_count}")
    print(f"Propiedades Locales: {local_count}")
    
    # Verificar que las propiedades Propify tengan coordenadas
    print("\n--- VERIFICACIÓN DE COORDENADAS PROPIY ---")
    propify_con_coordenadas = 0
    for prop in object_list:
        if isinstance(prop, dict) and prop.get('es_propify'):
            lat = prop.get('lat')
            lng = prop.get('lng')
            if lat is not None and lng is not None:
                propify_con_coordenadas += 1
    
    print(f"Propiedades Propify con coordenadas: {propify_con_coordenadas}/{propify_count}")
    
    # Verificar el template
    print("\n--- VERIFICACIÓN DEL TEMPLATE ---")
    template_path = 'ingestas/lista_propiedades_rediseno.html'
    
    # Leer el template
    from django.template.loader import get_template
    try:
        template = get_template(template_path)
        print(f"Template cargado: {template}")
        
        # Renderizar un fragmento simple para prueba
        test_context = {
            'propiedad': {
                'id': 999,
                'es_propify': True,
                'es_externo': True,
                'tipo_propiedad': 'Casa',
                'precio_usd': 150000,
                'departamento': 'Lima',
                'lat': -12.0464,
                'lng': -77.0428,
                'codigo': 'TEST001'
            }
        }
        
        # Probar la renderización de una tarjeta
        test_template = """
        <div class="property-card" data-es-propify="{{ propiedad.es_propify|default:'false' }}">
          {% if propiedad.es_propify %}
          <span class="badge bg-success">Propify</span>
          {% endif %}
          {{ propiedad.tipo_propiedad }}
        </div>
        """
        
        t = Template(test_template)
        result = t.render(Context(test_context))
        print(f"Renderización de prueba: {result}")
        
    except Exception as e:
        print(f"Error al cargar template: {e}")
    
    # Verificar los checkboxes en el contexto
    print("\n--- VERIFICACIÓN DE CHECKBOXES ---")
    checkboxes = context.get('checkboxes', {})
    print(f"Checkboxes en contexto: {checkboxes}")
    
    # Verificar si el filtro está funcionando
    print("\n--- VERIFICACIÓN DEL FILTRO ---")
    print(f"Parámetros GET: {dict(request.GET)}")
    
    # Llamar directamente a _calcular_checkboxes
    checkboxes_calculados = view._calcular_checkboxes()
    print(f"Checkboxes calculados: {checkboxes_calculados}")

def verificar_vista_directamente():
    """Verificar la vista llamando a sus métodos directamente"""
    print("\n=== VERIFICACIÓN DIRECTA DE LA VISTA ===")
    
    # Crear una request
    factory = RequestFactory()
    request = factory.get('/ingestas/propiedades/', {'fuente_propify': 'propify'})
    request.user = None
    
    # Instanciar la vista
    view = ListaPropiedadesView()
    view.setup(request)
    
    # Llamar a get_queryset
    print("\n--- get_queryset() ---")
    queryset = view.get_queryset()
    print(f"Queryset: {queryset}")
    print(f"Tipo: {type(queryset)}")
    
    # Llamar a _obtener_todas_propiedades
    print("\n--- _obtener_todas_propiedades() ---")
    try:
        todas_propiedades = view._obtener_todas_propiedades()
        print(f"Total propiedades obtenidas: {len(todas_propiedades)}")
        
        # Contar por tipo
        propify = [p for p in todas_propiedades if isinstance(p, dict) and p.get('es_propify')]
        externas = [p for p in todas_propiedades if isinstance(p, dict) and p.get('es_externo') and not p.get('es_propify')]
        locales = [p for p in todas_propiedades if isinstance(p, dict) and not p.get('es_externo')]
        
        print(f"Propify: {len(propify)}")
        print(f"Externas: {len(externas)}")
        print(f"Locales: {len(locales)}")
        
        # Mostrar primera propiedad Propify
        if propify:
            print(f"\nPrimera propiedad Propify:")
            primera = propify[0]
            for key in ['id', 'es_propify', 'es_externo', 'tipo_propiedad', 'lat', 'lng', 'codigo']:
                print(f"  {key}: {primera.get(key)}")
        
    except Exception as e:
        print(f"Error en _obtener_todas_propiedades: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verificar_contexto_filtro_propify()
    verificar_vista_directamente()
    print("\n=== VERIFICACIÓN COMPLETADA ===")