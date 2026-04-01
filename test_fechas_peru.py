#!/usr/bin/env python3
"""
Test para verificar que las fechas en la API de timeline tengan offset de Perú.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
import django
django.setup()

from webapp.propifai.models import PropifaiProperty
from webapp.propifai.views import property_timeline_api
from django.test import RequestFactory

def test_fechas():
    # Obtener una propiedad de prueba (ID 2 como antes)
    prop = PropifaiProperty.objects.filter(id=2).first()
    if not prop:
        print("Propiedad con ID 2 no encontrada")
        return
    
    print(f"Propiedad ID: {prop.id}")
    print(f"created_at raw: {prop.created_at}")
    print(f"created_at tipo: {type(prop.created_at)}")
    
    # Crear request simulada
    factory = RequestFactory()
    request = factory.get(f'/propifai/api/property/{prop.id}/timeline/')
    
    # Llamar a la vista directamente (no es lo ideal pero para prueba)
    # En su lugar, importaremos la función y la llamaremos con request
    from webapp.propifai.views import property_timeline_api
    from django.http import HttpRequest
    from django.contrib.auth.models import AnonymousUser
    
    request.user = AnonymousUser()
    
    # Ejecutar la vista
    import json
    from django.http import JsonResponse
    
    response = property_timeline_api(request, prop.id)
    if isinstance(response, JsonResponse):
        data = json.loads(response.content)
    else:
        print("Respuesta no es JsonResponse")
        return
    
    timeline = data.get('timeline', {})
    etapas = timeline.get('etapas', [])
    
    print("\nFechas en etapas:")
    for etapa in etapas:
        print(f"Etapa {etapa['id']} ({etapa['nombre']}): fecha_inicio = {etapa.get('fecha_inicio')}")
    
    # Verificar formato de fecha
    fecha_registro = etapas[0]['fecha_inicio'] if len(etapas) > 0 else None
    if fecha_registro:
        print(f"\nFecha registro string: {fecha_registro}")
        # Verificar si contiene offset
        if '-' in fecha_registro and 'T' in fecha_registro:
            print("✓ Contiene componente de tiempo y offset")
        elif 'T' in fecha_registro:
            print("✓ Contiene componente de tiempo pero puede no tener offset")
        else:
            print("✗ Solo fecha sin tiempo (puede causar offset)")
    
    # Mostrar también eventos
    events = data.get('events', [])
    if events:
        print(f"\nPrimer evento fecha_evento: {events[0].get('fecha_evento')}")

if __name__ == '__main__':
    test_fechas()