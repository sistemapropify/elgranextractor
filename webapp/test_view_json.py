#!/usr/bin/env python
import sys
import os

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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

# Crear request simulada
rf = RequestFactory()
request = rf.get('/propifai/dashboard/visitas/')

# Ejecutar vista
response = property_visits_dashboard(request)

print(f"Status: {response.status_code}")
print(f"Content-Type: {response['Content-Type']}")

# Obtener el contexto (no directamente accesible desde response)
# En su lugar, vamos a inspeccionar el contenido HTML
content = response.content.decode('utf-8')

# Buscar properties_json en el template
if 'properties_json' in content:
    print("\n✓ 'properties_json' encontrado en el HTML")
    
    # Buscar la línea donde se asigna propertiesData
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'propertiesData' in line and 'const' in line:
            print(f"\nLínea {i+1}: {line.strip()}")
            
            # Extraer el valor entre = y ;
            import re
            match = re.search(r'const propertiesData\s*=\s*(.*?);', line)
            if match:
                value = match.group(1)
                print(f"Valor asignado: {value[:200]}...")
                
                # Verificar si es JSON válido o una variable template
                if value.strip().startswith('{{') and value.strip().endswith('}}'):
                    print("✗ ERROR: La variable template no fue renderizada")
                    print("  Esto significa que properties_json no está en el contexto")
                elif value.strip() == '[]':
                    print("✓ JSON es un array vacío []")
                elif value.strip().startswith('['):
                    print("✓ JSON parece ser un array")
                    # Intentar parsear
                    try:
                        data = json.loads(value)
                        print(f"  JSON parseado: {len(data)} elementos")
                        if len(data) > 0:
                            print(f"  Primer elemento: {json.dumps(data[0], indent=2)[:200]}...")
                    except json.JSONDecodeError as e:
                        print(f"✗ Error parseando JSON: {e}")
                else:
                    print(f"  Valor inesperado: {value[:100]}")
            break
else:
    print("\n✗ 'properties_json' NO encontrado en el HTML")

# También buscar en el contexto de la vista (necesitamos acceder de otra manera)
print("\n=== VERIFICANDO LA VISTA DIRECTAMENTE ===")
# Llamar a la función y capturar lo que pasa al template
from django.template import Template, Context
import io
from django.http import HttpResponse

# Simular la vista manualmente
from propifai.models import PropifaiProperty, Event
from django.db.models import Count, Min, Max, Case, When, Value, BooleanField
import json
from datetime import date

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

properties_list = []
for prop in properties:
    status_name = prop.availability_status if prop.availability_status else 'Sin estado'
    distrito_name = prop.district if prop.district else 'Sin distrito'
    zona_name = prop.urbanization if prop.urbanization else 'Sin zona'
    tipo_name = 'Propiedad'
    
    dias_en_cartera = 0
    if prop.created_at:
        hoy = date.today()
        dias_en_cartera = (hoy - prop.created_at.date()).days
    
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

properties_json = json.dumps(properties_list)
print(f"properties_json generado: {len(properties_json)} caracteres")
print(f"Número de propiedades: {len(properties_list)}")
if properties_list:
    print(f"Primera propiedad: {properties_list[0]['code']} con {properties_list[0]['total_eventos']} eventos")

# Verificar si el JSON es válido
try:
    parsed = json.loads(properties_json)
    print(f"✓ JSON válido, {len(parsed)} elementos")
except Exception as e:
    print(f"✗ JSON inválido: {e}")