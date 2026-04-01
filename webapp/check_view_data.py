#!/usr/bin/env python
import sys
import os

# Añadir el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    import django
    django.setup()
except ImportError:
    print("Error: No se pudo importar Django")
    sys.exit(1)

from propifai.models import PropifaiProperty, Event
from django.db.models import Count, Min, Max, Case, When, Value, BooleanField
import json
from datetime import date

print("=== VERIFICACIÓN DE DATOS PARA EL DASHBOARD ===")

# 1. Verificar conteo de propiedades
total_props = PropifaiProperty.objects.count()
print(f"1. Total de propiedades en la base de datos: {total_props}")

# 2. Verificar conteo de eventos
total_events = Event.objects.count()
print(f"2. Total de eventos en la base de datos: {total_events}")

# 3. Ejecutar la misma consulta que la vista
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

print(f"3. Propiedades después de anotaciones: {properties.count()}")

# 4. Contar propiedades con eventos
props_con_eventos = properties.filter(total_eventos__gt=0)
print(f"4. Propiedades con al menos un evento: {props_con_eventos.count()}")

# 5. Simular la serialización que hace la vista
properties_list = []
for prop in properties[:5]:  # Solo las primeras 5 para ejemplo
    status_name = prop.availability_status if prop.availability_status else 'Sin estado'
    distrito_name = prop.district if prop.district else 'Sin distrito'
    zona_name = prop.urbanization if prop.urbanization else 'Sin zona'
    tipo_name = 'Propiedad'  # Simplificado
    
    # Calcular días en cartera
    dias_en_cartera = 0
    if prop.created_at:
        hoy = date.today()
        dias_en_cartera = (hoy - prop.created_at.date()).days
    
    # Calcular frecuencia de visitas
    frecuencia_visitas = 'N/A'
    if prop.primera_visita and prop.ultima_visita and prop.total_eventos > 1:
        dias = (prop.ultima_visita - prop.primera_visita).days
        frecuencia_visitas = f"{(dias / (prop.total_eventos - 1)):.1f} días"
    
    properties_list.append({
        'id': prop.id,
        'code': prop.code,
        'title': prop.title,
        'address': prop.real_address or prop.exact_address or 'Sin dirección',
        'property_type': tipo_name,
        'district': distrito_name,
        'zone': zona_name,
        'status': status_name,
        'status_code': prop.availability_status,
        'price': float(prop.price) if prop.price else None,
        'agent_name': 'Sin agente',
        'total_eventos': prop.total_eventos,
        'primera_visita': prop.primera_visita.isoformat() if prop.primera_visita else None,
        'ultima_visita': prop.ultima_visita.isoformat() if prop.ultima_visita else None,
        'tiene_lead': prop.tiene_lead,
        'tiene_propuesta': prop.tiene_propuesta,
        'dias_en_cartera': dias_en_cartera,
        'frecuencia_visitas': frecuencia_visitas,
        'created_at': prop.created_at.isoformat() if prop.created_at else None,
    })

print(f"\n5. Ejemplo de serialización (primera propiedad):")
if properties_list:
    first_prop = properties_list[0]
    print(f"   ID: {first_prop['id']}")
    print(f"   Código: {first_prop['code']}")
    print(f"   Título: {first_prop['title']}")
    print(f"   Total eventos: {first_prop['total_eventos']}")
    print(f"   Primera visita: {first_prop['primera_visita']}")
    print(f"   Última visita: {first_prop['ultima_visita']}")
    print(f"   Tiene lead: {first_prop['tiene_lead']}")
    print(f"   Tiene propuesta: {first_prop['tiene_propuesta']}")
    
    # Verificar que el JSON se puede serializar
    try:
        json_str = json.dumps(properties_list)
        print(f"\n6. JSON serializado correctamente")
        print(f"   Longitud del JSON: {len(json_str)} caracteres")
        print(f"   Número de propiedades en JSON: {len(properties_list)}")
    except Exception as e:
        print(f"\n6. ERROR al serializar JSON: {e}")
else:
    print("   No hay propiedades para serializar")

# 7. Verificar la vista directamente
print("\n7. Probando la vista directamente...")
try:
    from django.test import RequestFactory
    from propifai.views import property_visits_dashboard
    
    rf = RequestFactory()
    request = rf.get('/propifai/dashboard/visitas/')
    response = property_visits_dashboard(request)
    
    print(f"   Status code: {response.status_code}")
    print(f"   Content-Type: {response['Content-Type']}")
    
    # Verificar si es HTML
    content = response.content.decode('utf-8')
    if 'properties_json' in content:
        print("   ✓ Variable properties_json encontrada en HTML")
        
        # Buscar el JSON
        import re
        pattern = r'const propertiesData = (.*?);'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            print(f"   ✓ JSON extraído del HTML")
            print(f"   Longitud del JSON en HTML: {len(json_str)} caracteres")
            
            # Verificar si es un array vacío
            if json_str == '[]':
                print("   ⚠ ADVERTENCIA: JSON es un array vacío []")
            elif len(json_str) < 10:
                print(f"   ⚠ ADVERTENCIA: JSON muy corto: {json_str}")
            else:
                print(f"   ✓ JSON parece tener datos")
        else:
            print("   ✗ No se pudo extraer propertiesData del JavaScript")
    else:
        print("   ✗ Variable properties_json NO encontrada en HTML")
        
except Exception as e:
    print(f"   ERROR al probar la vista: {e}")

print("\n=== FIN DE VERIFICACIÓN ===")