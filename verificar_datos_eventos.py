#!/usr/bin/env python
"""
Script para verificar los datos de eventos y ver si se están mostrando correctamente.
"""
import os
import sys
import django
from datetime import datetime

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from eventos.models import Event, EventType
from propifai.models import User, PropifaiProperty

def verificar_datos():
    print("=== Verificación de datos de eventos ===")
    
    # Contar eventos
    total = Event.objects.count()
    print(f"Total eventos en BD: {total}")
    
    # Verificar algunos eventos recientes
    eventos = Event.objects.all().order_by('-fecha_evento', '-hora_inicio')[:10]
    
    print("\n=== Últimos 10 eventos ===")
    for i, evento in enumerate(eventos, 1):
        print(f"\n{i}. ID: {evento.id}, Código: {evento.code}")
        print(f"   Fecha: {evento.fecha_evento}, Hora: {evento.hora_inicio}")
        print(f"   Propiedad ID: {evento.property_id}")
        print(f"   Agente ID: {evento.assigned_agent_id}")
        print(f"   Tipo evento ID: {evento.event_type_id}")
        print(f"   Estado: {evento.status}")
        
        # Verificar si existe el agente
        if evento.assigned_agent_id:
            try:
                usuario = User.objects.get(id=evento.assigned_agent_id)
                nombre = f"{usuario.first_name} {usuario.last_name}".strip()
                print(f"   Agente encontrado: {nombre} (ID: {usuario.id})")
            except User.DoesNotExist:
                print(f"   ✗ Agente con ID {evento.assigned_agent_id} NO existe en tabla User")
            except Exception as e:
                print(f"   Error al buscar agente: {e}")
        
        # Verificar si existe la propiedad
        if evento.property_id:
            try:
                prop = PropifaiProperty.objects.get(id=evento.property_id)
                print(f"   Propiedad encontrada: {prop.title[:50]}... (ID: {prop.id})")
                print(f"   Coordenadas: {prop.coordinates}")
            except PropifaiProperty.DoesNotExist:
                print(f"   ✗ Propiedad con ID {evento.property_id} NO existe en tabla PropifaiProperty")
            except Exception as e:
                print(f"   Error al buscar propiedad: {e}")
    
    # Verificar tipos de evento
    print("\n=== Tipos de evento activos ===")
    tipos = EventType.objects.filter(is_active=True)
    for tipo in tipos:
        print(f"  ID: {tipo.id}, Nombre: {tipo.name}, Color: {tipo.color}")
    
    # Verificar estadísticas
    from datetime import date, timedelta
    hoy = date.today()
    eventos_hoy = Event.objects.filter(fecha_evento=hoy).count()
    eventos_semana = Event.objects.filter(fecha_evento__gte=hoy - timedelta(days=7)).count()
    
    print(f"\n=== Estadísticas ===")
    print(f"Eventos hoy ({hoy}): {eventos_hoy}")
    print(f"Eventos última semana: {eventos_semana}")
    
    # Verificar si hay datos inconsistentes
    print("\n=== Verificación de integridad ===")
    
    # Eventos sin agente pero con assigned_agent_id
    eventos_sin_agente_valido = []
    for evento in Event.objects.filter(assigned_agent_id__isnull=False):
        if not User.objects.filter(id=evento.assigned_agent_id).exists():
            eventos_sin_agente_valido.append(evento.id)
    
    if eventos_sin_agente_valido:
        print(f"Eventos con assigned_agent_id que no existe en User: {eventos_sin_agente_valido[:10]}")
    else:
        print("✓ Todos los assigned_agent_id tienen usuario correspondiente")
    
    # Eventos sin propiedad válida
    eventos_sin_propiedad_valida = []
    for evento in Event.objects.filter(property_id__isnull=False):
        if not PropifaiProperty.objects.filter(id=evento.property_id).exists():
            eventos_sin_propiedad_valida.append(evento.id)
    
    if eventos_sin_propiedad_valida:
        print(f"Eventos con property_id que no existe en PropifaiProperty: {eventos_sin_propiedad_valida[:10]}")
    else:
        print("✓ Todos los property_id tienen propiedad correspondiente")

if __name__ == "__main__":
    verificar_datos()