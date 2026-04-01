import sys
sys.path.append('d:/proyectos/prometeo')
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
import django
django.setup()

from propifai.models import PropifaiProperty, Event
from django.db import connections

property_id = 2

print('=== DATOS CRUDOS DE PROPIEDAD ===')
prop = PropifaiProperty.objects.get(id=property_id)
print(f'ID: {prop.id}')
print(f'Código: {prop.code}')
print(f'created_at: {prop.created_at} (tipo: {type(prop.created_at)})')
print(f'updated_at: {prop.updated_at}')
print(f'availability_status: {prop.availability_status}')
print(f'price: {prop.price}, built_area: {prop.built_area}')

# Obtener wp_last_sync desde la tabla properties
conn = connections['propifai']
with conn.cursor() as cursor:
    cursor.execute("""
        SELECT wp_post_id, wp_last_sync
        FROM properties
        WHERE id = %s
    """, [property_id])
    row = cursor.fetchone()
    if row:
        print(f'wp_post_id: {row[0]}, wp_last_sync: {row[1]} (tipo: {type(row[1])})')
    else:
        print('No encontrado en tabla properties')

print('\n=== EVENTOS DE LA PROPIEDAD ===')
events = Event.objects.filter(property_id=property_id).select_related('event_type').order_by('fecha_evento')
for e in events:
    print(f"Evento ID {e.id}: {e.titulo} ({e.event_type.name if e.event_type else 'sin tipo'})")
    print(f"  fecha_evento: {e.fecha_evento}, proposal_id: {e.proposal_id}, lead_id: {e.lead_id}")
    print(f"  hora_inicio: {e.hora_inicio}, hora_fin: {e.hora_fin}")

print('\n=== CÁLCULO DE FECHAS SEGÚN LÓGICA ACTUAL ===')
# Fecha registro
fecha_registro = prop.created_at.date().isoformat() if prop.created_at else None
print(f'Fecha registro (date): {fecha_registro}')

# Fecha publicación
wp_last_sync = row[1] if row else None
fecha_publicacion = fecha_registro
if wp_last_sync:
    if hasattr(wp_last_sync, 'date'):
        fecha_publicacion = wp_last_sync.date().isoformat()
    elif isinstance(wp_last_sync, str):
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(wp_last_sync.replace('Z', '+00:00'))
            fecha_publicacion = dt.date().isoformat()
        except:
            pass
print(f'Fecha publicación (wp_last_sync): {fecha_publicacion}')

# Fecha primera visita
visita_events = [e for e in events if e.event_type and 'visita' in e.event_type.name.lower()]
primera_visita = visita_events[0].fecha_evento.date().isoformat() if visita_events else None
print(f'Fecha primera visita: {primera_visita}')

# Fecha primera propuesta
propuesta_events = [e for e in events if e.proposal_id]
primera_propuesta = propuesta_events[0].fecha_evento.date().isoformat() if propuesta_events else None
print(f'Fecha primera propuesta: {primera_propuesta}')

# Fecha cierre (si está vendida)
fecha_cierre = prop.updated_at.date().isoformat() if prop.availability_status == 'sold' else None
print(f'Fecha cierre (updated_at): {fecha_cierre}')

print('\n=== COMPARACIÓN CON API ===')
import requests
resp = requests.get(f'http://localhost:8000/propifai/api/property/{property_id}/timeline/')
if resp.status_code == 200:
    data = resp.json()
    etapas = data.get('timeline', {}).get('etapas', [])
    for etapa in etapas:
        print(f"Etapa {etapa['id']} ({etapa['nombre']}): {etapa['fecha_inicio']}")
else:
    print('Error al obtener API')