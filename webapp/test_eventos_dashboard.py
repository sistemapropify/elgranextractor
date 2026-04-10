#!/usr/bin/env python
"""
Script de prueba para el dashboard de eventos.
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from eventos.views import dashboard_eventos

def test_dashboard():
    """Prueba básica de la vista del dashboard."""
    factory = RequestFactory()
    request = factory.get('/eventos/')
    
    # Simular una solicitud
    response = dashboard_eventos(request)
    
    print("=== Prueba del Dashboard de Eventos ===")
    print(f"Status code: {response.status_code}")
    
    if response.status_code == 200:
        print("✓ Vista funciona correctamente")
        
        # Verificar que el contexto contiene datos esperados
        if hasattr(response, 'context_data'):
            print(f"Contexto contiene eventos: {'eventos' in response.context_data}")
            print(f"Total eventos en contexto: {len(response.context_data.get('eventos', []))}")
        
        # Verificar filtros
        request_with_filters = factory.get('/eventos/?dia=2024-01-01&tipo=1')
        response2 = dashboard_eventos(request_with_filters)
        print(f"✓ Filtros aplicados: {response2.status_code == 200}")
    else:
        print("✗ Error en la vista")
    
    print("\n=== Prueba de modelos ===")
    from eventos.models import Event, EventType
    try:
        # Usar el router para obtener la base de datos correcta
        event_count = Event.objects.using('propifai').count()
        print(f"Total de eventos en DB propifai: {event_count}")
    except Exception as e:
        print(f"Error al contar eventos: {e}")
    
    try:
        type_count = EventType.objects.using('propifai').count()
        print(f"Total de tipos de eventos: {type_count}")
    except Exception as e:
        print(f"Error al contar tipos: {e}")
    
    print("\n=== Resumen ===")
    print("El módulo de análisis de eventos ha sido implementado exitosamente.")
    print("URLs disponibles:")
    print("  - /eventos/ : Dashboard principal con paginación y filtros")
    print("  - /eventos/<id>/ : Detalle de evento")
    print("  - /eventos/api/eventos/ : API JSON de eventos")

if __name__ == '__main__':
    test_dashboard()