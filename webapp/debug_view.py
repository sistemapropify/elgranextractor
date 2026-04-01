#!/usr/bin/env python
"""
Script para depurar la vista property_visits_dashboard.
"""
import sys
import os

# Cambiar al directorio actual
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Configurar Django
sys.path.insert(0, os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    import django
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

from django.test import RequestFactory
from propifai.views import property_visits_dashboard
import json

def debug_view():
    print("=== DEBUG DE LA VISTA property_visits_dashboard ===")
    
    # Crear request simulada
    rf = RequestFactory()
    request = rf.get('/propifai/dashboard/visitas/')
    
    # Ejecutar vista
    response = property_visits_dashboard(request)
    
    print(f"Status code: {response.status_code}")
    print(f"Content-Type: {response['Content-Type']}")
    
    # Verificar si es HTML
    content = response.content.decode('utf-8')
    
    # Buscar properties_json en el contexto (no podemos acceder directamente)
    # En su lugar, busquemos en el HTML
    if 'properties_json' in content:
        print("✓ Variable properties_json encontrada en HTML")
        
        # Extraer el valor
        import re
        pattern = r'const propertiesData = (.*?);'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            print(f"JSON encontrado (primeros 200 chars): {json_str[:200]}...")
            
            # Intentar parsear
            try:
                data = json.loads(json_str)
                print(f"✓ JSON parseado correctamente")
                print(f"  Número de propiedades: {len(data)}")
                if len(data) > 0:
                    print(f"  Primera propiedad ID: {data[0].get('id')}")
                    print(f"  Primera propiedad título: {data[0].get('title')}")
                    print(f"  Total eventos primera propiedad: {data[0].get('total_eventos')}")
            except json.JSONDecodeError as e:
                print(f"✗ Error parseando JSON: {e}")
                print(f"  JSON string: {json_str[:500]}")
        else:
            print("✗ No se pudo extraer propertiesData del JavaScript")
    else:
        print("✗ Variable properties_json NO encontrada en HTML")
        
        # Buscar otras pistas
        if 'propertiesData' in content:
            print("  (pero propertiesData aparece en el código)")
            
    # Verificar si hay errores en el HTML
    if 'console.error' in content:
        print("⚠ Se encontraron console.error en el HTML")
        
    # Guardar un fragmento para inspección
    with open('debug_fragment.html', 'w', encoding='utf-8') as f:
        f.write(content[:5000])
    print("\nFragmento guardado en debug_fragment.html")
    
    # También probar la consulta de base de datos directamente
    print("\n=== CONSULTA DIRECTA A BASE DE DATOS ===")
    from propifai.models import PropifaiProperty, Event
    from django.db.models import Count, Min, Max, Case, When, Value, BooleanField
    
    properties = PropifaiProperty.objects.all()
    properties = properties.annotate(
        total_eventos=Count('event', distinct=True),
        primera_visita=Min('event__fecha_evento'),
        ultima_visita=Max('event__fecha_evento'),
        tiene_lead=Case(
            When(event__lead_id__isnull=False, then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        ),
        tiene_propuesta=Case(
            When(event__proposal_id__isnull=False, then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        )
    ).distinct()
    
    print(f"Total propiedades en consulta: {properties.count()}")
    
    # Contar propiedades con eventos
    props_con_eventos = properties.filter(total_eventos__gt=0)
    print(f"Propiedades con eventos: {props_con_eventos.count()}")
    
    # Mostrar algunas propiedades
    for i, prop in enumerate(properties[:3]):
        print(f"\nPropiedad {i+1}:")
        print(f"  ID: {prop.id}")
        print(f"  Código: {prop.code}")
        print(f"  Título: {prop.title}")
        print(f"  Total eventos: {prop.total_eventos}")
        print(f"  Primera visita: {prop.primera_visita}")
        print(f"  Última visita: {prop.ultima_visita}")

if __name__ == "__main__":
    debug_view()