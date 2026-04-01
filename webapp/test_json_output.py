#!/usr/bin/env python
import os
import sys
import django
import json
from datetime import date

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prometeo.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from propifai.models import PropifaiProperty, Event
from django.db.models import Count, Min, Max, Case, When, Value, BooleanField

print("=== TEST JSON OUTPUT ===")

# Obtener propiedades con anotaciones
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

print(f"Total propiedades: {properties.count()}")
print(f"Propiedades con eventos: {properties.filter(total_eventos__gt=0).count()}")

# Serializar a JSON
properties_list = []
for prop in properties[:3]:  # Solo las primeras 3 para ver
    status_name = prop.availability_status if prop.availability_status else 'Sin estado'
    distrito_name = prop.district if prop.district else 'Sin distrito'
    tipo_name = prop.tipo_propiedad if hasattr(prop, 'tipo_propiedad') else 'Propiedad'
    
    dias_en_cartera = 0
    if prop.created_at:
        hoy = date.today()
        dias_en_cartera = (hoy - prop.created_at.date()).days
    
    prop_dict = {
        'id': prop.id,
        'code': prop.code,
        'title': prop.title,
        'address': prop.real_address or prop.exact_address or 'Sin dirección',
        'property_type': tipo_name,
        'district': distrito_name,
        'status': status_name,
        'agent_name': 'Sin agente',
        'total_eventos': prop.total_eventos,
        'primera_visita': prop.primera_visita.isoformat() if prop.primera_visita else None,
        'ultima_visita': prop.ultima_visita.isoformat() if prop.ultima_visita else None,
        'tiene_lead': prop.tiene_lead,
        'tiene_propuesta': prop.tiene_propuesta,
        'dias_en_cartera': dias_en_cartera,
    }
    properties_list.append(prop_dict)

print("\nJSON generado (primeros 3 elementos):")
json_str = json.dumps(properties_list, indent=2, ensure_ascii=False)
print(json_str)

# Verificar si es JSON válido
try:
    parsed = json.loads(json_str)
    print("\n✓ JSON válido")
except json.JSONDecodeError as e:
    print(f"\n✗ Error en JSON: {e}")

# Verificar la vista completa
print("\n=== TEST VISTA COMPLETA ===")
from django.test import RequestFactory
from propifai.views import property_visits_dashboard

factory = RequestFactory()
request = factory.get('/propifai/dashboard/visitas/')
response = property_visits_dashboard(request)

print(f"Status code: {response.status_code}")
print(f"Template: {response.template_name}")

# Obtener contexto
if hasattr(response, 'context_data'):
    context = response.context_data
    print(f"Context keys: {list(context.keys())}")
    
    if 'properties_json' in context:
        json_data = context['properties_json']
        print(f"\nJSON en contexto (primeros 500 chars):")
        print(str(json_data)[:500])
        
        # Verificar si es JSON válido
        try:
            parsed_json = json.loads(json_data)
            print(f"\n✓ JSON en contexto es válido")
            print(f"  Número de propiedades: {len(parsed_json)}")
        except (TypeError, json.JSONDecodeError) as e:
            print(f"\n✗ Error en JSON del contexto: {e}")
            print(f"  Tipo: {type(json_data)}")
            print(f"  Valor: {json_data}")