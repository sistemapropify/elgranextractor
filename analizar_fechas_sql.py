import sys
sys.path.append('d:/proyectos/prometeo')
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
# No llamar a django.setup, usar conexiones directamente
from django.db import connections
from datetime import datetime

property_id = 2

print('=== DATOS CRUDOS DE PROPIEDAD (desde base de datos) ===')
# Conectar a la base de datos default (propifai?)
conn = connections['propifai']
with conn.cursor() as cursor:
    cursor.execute("""
        SELECT id, code, title, price, built_area, availability_status,
               created_at, updated_at, district, urbanization
        FROM propifai_properties
        WHERE id = %s
    """, [property_id])
    row = cursor.fetchone()
    if row:
        print(f'ID: {row[0]}, Código: {row[1]}, Título: {row[2]}')
        print(f'Precio: {row[3]}, Área construida: {row[4]}')
        print(f'Estado: {row[5]}')
        print(f'created_at: {row[6]} (tipo: {type(row[6])})')
        print(f'updated_at: {row[7]}')
    else:
        print('Propiedad no encontrada en propifai_properties')
        sys.exit(1)

# Obtener wp_last_sync desde la tabla properties (en la misma BD propifai)
with conn.cursor() as cursor:
    cursor.execute("""
        SELECT wp_post_id, wp_last_sync
        FROM properties
        WHERE id = %s
    """, [property_id])
    row2 = cursor.fetchone()
    if row2:
        print(f'wp_post_id: {row2[0]}, wp_last_sync: {row2[1]} (tipo: {type(row2[1])})')
        wp_last_sync = row2[1]
    else:
        print('No encontrado en tabla properties')
        wp_last_sync = None

print('\n=== EVENTOS DE LA PROPIEDAD ===')
with conn.cursor() as cursor:
    cursor.execute("""
        SELECT e.id, e.titulo, e.fecha_evento, e.hora_inicio, e.hora_fin,
               e.proposal_id, e.lead_id, et.name as event_type_name
        FROM events e
        LEFT JOIN event_types et ON e.event_type_id = et.id
        WHERE e.property_id = %s
        ORDER BY e.fecha_evento
    """, [property_id])
    events = cursor.fetchall()
    for e in events:
        print(f"Evento ID {e[0]}: {e[1]} ({e[7]})")
        print(f"  fecha_evento: {e[2]}, proposal_id: {e[5]}, lead_id: {e[6]}")
        print(f"  hora_inicio: {e[3]}, hora_fin: {e[4]}")

print('\n=== CÁLCULO DE FECHAS SEGÚN LÓGICA ACTUAL ===')
# Fecha registro
created_at = row[6]
fecha_registro = created_at.date().isoformat() if created_at else None
print(f'Fecha registro (date): {fecha_registro}')

# Fecha publicación
fecha_publicacion = fecha_registro
if wp_last_sync:
    if hasattr(wp_last_sync, 'date'):
        fecha_publicacion = wp_last_sync.date().isoformat()
    elif isinstance(wp_last_sync, str):
        try:
            dt = datetime.fromisoformat(wp_last_sync.replace('Z', '+00:00'))
            fecha_publicacion = dt.date().isoformat()
        except:
            pass
print(f'Fecha publicación (wp_last_sync): {fecha_publicacion}')

# Fecha primera visita
visita_events = [e for e in events if e[7] and 'visita' in e[7].lower()]
primera_visita = visita_events[0][2].date().isoformat() if visita_events else None
print(f'Fecha primera visita: {primera_visita}')

# Fecha primera propuesta
propuesta_events = [e for e in events if e[5]]
primera_propuesta = propuesta_events[0][2].date().isoformat() if propuesta_events else None
print(f'Fecha primera propuesta: {primera_propuesta}')

# Fecha cierre (si está vendida)
availability_status = row[5]
updated_at = row[7]
fecha_cierre = updated_at.date().isoformat() if availability_status == 'sold' else None
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