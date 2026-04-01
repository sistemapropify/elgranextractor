#!/usr/bin/env python
"""
Script para debuggear los datos reales que llegan desde la vista.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from propifai.models import PropifaiProperty, Event
from propifai.views import property_visits_dashboard
from django.test import RequestFactory
import json

def debug_real_data():
    """Debug de datos reales"""
    print("=== DEBUG DE DATOS REALES DEL DASHBOARD ===")
    
    # Crear una request simulada
    factory = RequestFactory()
    request = factory.get('/propifai/dashboard/visitas/')
    
    # Llamar a la vista
    from propifai.views import property_visits_dashboard
    response = property_visits_dashboard(request)
    
    # Obtener el contexto
    context = response.context_data if hasattr(response, 'context_data') else {}
    
    print("\n1. CONTEXTO DE LA VISTA:")
    for key, value in context.items():
        if key == 'properties_json':
            print(f"   {key}: (JSON con {len(value) if isinstance(value, str) else '?'} caracteres)")
            try:
                data = json.loads(value)
                print(f"      - {len(data)} propiedades en JSON")
                if data:
                    print(f"      - Primera propiedad:")
                    for k, v in data[0].items():
                        print(f"        {k}: {v}")
            except:
                print(f"      - Error al parsear JSON")
        else:
            print(f"   {key}: {type(value)}")
    
    print("\n2. DATOS DIRECTOS DE LA BASE DE DATOS:")
    
    # Obtener algunas propiedades directamente
    properties = PropifaiProperty.objects.all()[:5]
    print(f"   Total propiedades en DB: {PropifaiProperty.objects.count()}")
    
    for i, prop in enumerate(properties):
        print(f"\n   Propiedad {i+1}: {prop.code}")
        print(f"      - ID: {prop.id}")
        print(f"      - Título: {prop.title}")
        print(f"      - Dirección: {prop.address}")
        print(f"      - Distrito: {prop.district}")
        print(f"      - Zona: {prop.zone}")
        print(f"      - Estado: {prop.status}")
        print(f"      - Precio: {prop.price}")
        print(f"      - Agente: {prop.agent_name}")
        print(f"      - Fecha creación: {prop.created_at}")
        
        # Contar eventos
        event_count = Event.objects.filter(property=prop).count()
        print(f"      - Eventos asociados: {event_count}")
        
        if event_count > 0:
            events = Event.objects.filter(property=prop).order_by('fecha_evento')[:3]
            for j, event in enumerate(events):
                print(f"        Evento {j+1}: {event.titulo} - {event.fecha_evento}")
    
    print("\n3. VERIFICACIÓN DE CAMPOS EN MODELOS:")
    print("   Campos de PropifaiProperty:")
    for field in PropifaiProperty._meta.fields:
        print(f"      - {field.name}: {field.get_internal_type()}")
    
    print("\n   Campos de Event:")
    for field in Event._meta.fields:
        print(f"      - {field.name}: {field.get_internal_type()}")

if __name__ == "__main__":
    debug_real_data()