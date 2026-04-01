import sys
sys.path.append('d:/proyectos/prometeo')
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
# Evitar error de semillas importando solo conexiones
from django.db import connections
from datetime import datetime, timezone, timedelta

property_id = 2

print('=== INVESTIGACIÓN OFFSET DE FECHA ===')
conn = connections['propifai']
with conn.cursor() as cursor:
    cursor.execute("""
        SELECT id, code, created_at, updated_at
        FROM propifai_propifaiproperty
        WHERE id = %s
    """, [property_id])
    row = cursor.fetchone()
    if row:
        print(f'Propiedad ID: {row[0]}, Código: {row[1]}')
        created_at = row[2]
        updated_at = row[3]
        print(f'created_at (BD): {created_at} (tipo: {type(created_at)})')
        print(f'updated_at (BD): {updated_at}')
        
        # Convertir a datetime con zona horaria si es naive
        if created_at and created_at.tzinfo is None:
            # Asumir UTC
            created_at_utc = created_at.replace(tzinfo=timezone.utc)
        else:
            created_at_utc = created_at
        
        # Convertir a zona horaria de Perú (UTC-5)
        peru_tz = timezone(timedelta(hours=-5))
        created_at_peru = created_at_utc.astimezone(peru_tz)
        print(f'created_at (Perú): {created_at_peru}')
        print(f'Fecha Perú (date): {created_at_peru.date()}')
        print(f'Fecha UTC (date): {created_at_utc.date()}')
        
        # Diferencia de días
        diff = created_at_utc.date() - created_at_peru.date()
        print(f'Diferencia días (UTC - Perú): {diff.days}')
        
        # Lo que estamos enviando (date() del objeto naive)
        fecha_envio = created_at.date() if created_at else None
        print(f'Fecha que enviamos (created_at.date()): {fecha_envio}')
        
    else:
        print('Propiedad no encontrada')
        sys.exit(1)

# Obtener wp_last_sync
with conn.cursor() as cursor:
    cursor.execute("""
        SELECT wp_last_sync
        FROM properties
        WHERE id = %s
    """, [property_id])
    row = cursor.fetchone()
    if row:
        wp_last_sync = row[0]
        print(f'\nwp_last_sync (BD): {wp_last_sync} (tipo: {type(wp_last_sync)})')
        if wp_last_sync:
            if isinstance(wp_last_sync, str):
                # Parsear string
                try:
                    wp_last_sync = datetime.fromisoformat(wp_last_sync.replace('Z', '+00:00'))
                except:
                    pass
            if hasattr(wp_last_sync, 'date'):
                print(f'Fecha wp_last_sync (date): {wp_last_sync.date()}')
                # Convertir a Perú si tiene tzinfo
                if hasattr(wp_last_sync, 'tzinfo'):
                    wp_peru = wp_last_sync.astimezone(peru_tz)
                    print(f'wp_last_sync (Perú): {wp_peru.date()}')

print('\n=== LLAMADA A API ===')
import requests
resp = requests.get(f'http://localhost:8000/propifai/api/property/{property_id}/timeline/')
if resp.status_code == 200:
    data = resp.json()
    etapas = data.get('timeline', {}).get('etapas', [])
    for etapa in etapas:
        print(f"Etapa {etapa['id']} ({etapa['nombre']}): {etapa['fecha_inicio']} (estado: {etapa['estado']})")
else:
    print('Error API')

print('\n=== SIMULACIÓN FRONTEND ===')
# Simular lo que hace JavaScript con una fecha YYYY-MM-DD
fecha_str = '2026-01-07'
fecha_js = datetime.fromisoformat(fecha_str)  # Esto crea un datetime naive, tratado como local
print(f'Fecha string: {fecha_str}')
print(f'JS new Date(fecha_str): {fecha_js}')
print(f'JS toLocaleDateString("es-PE"): {fecha_js.strftime("%d/%m/%Y")}')  # No hay conversión de zona horaria porque es naive
# Pero en realidad JS interpreta como UTC medianoche
import pytz
fecha_utc = datetime.fromisoformat(fecha_str + 'T00:00:00+00:00')
fecha_peru = fecha_utc.astimezone(peru_tz)
print(f'Si JS interpreta como UTC: {fecha_utc.date()} -> Perú: {fecha_peru.date()} (diferencia: {(fecha_utc.date() - fecha_peru.date()).days})')