#!/usr/bin/env python
"""
Script para probar las mejoras del dashboard de eventos.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from eventos.models import Event
from propifai.models import PropifaiProperty

def test_mejoras():
    """Prueba las mejoras implementadas."""
    print("=== Prueba de mejoras del dashboard de eventos ===")
    
    # 1. Verificar que hay eventos con property_id
    eventos_con_propiedad = Event.objects.filter(property_id__isnull=False).count()
    print(f"1. Eventos con property_id: {eventos_con_propiedad}")
    
    # 2. Verificar que hay propiedades correspondientes
    if eventos_con_propiedad > 0:
        # Obtener algunos property_id de eventos
        property_ids = Event.objects.filter(property_id__isnull=False).values_list('property_id', flat=True)[:5]
        print(f"2. Primeros property_ids encontrados: {list(property_ids)}")
        
        # Verificar si existen en PropifaiProperty
        propiedades = PropifaiProperty.objects.filter(id__in=property_ids)
        print(f"3. Propiedades encontradas en PropifaiProperty: {propiedades.count()}")
        
        for prop in propiedades:
            print(f"   - ID: {prop.id}, Título: {prop.title}, Coordenadas: {prop.coordinates}")
            print(f"     Latitud: {prop.latitude}, Longitud: {prop.longitude}")
    
    # 3. Verificar la vista
    from django.test import Client
    client = Client()
    
    # Configurar ALLOWED_HOSTS para pruebas
    from django.conf import settings
    settings.ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
    
    response = client.get('/eventos/')
    print(f"\n4. Prueba de vista /eventos/: Status {response.status_code}")
    
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        
        # Verificar elementos nuevos
        if 'Propiedad' in content:
            print("   ✓ Columna 'Propiedad' encontrada")
        if 'Coordenadas' in content:
            print("   ✓ Columna 'Coordenadas' encontrada")
        if 'Ver Mapa' in content:
            print("   ✓ Botón 'Ver Mapa' encontrado")
        if 'mapModal' in content:
            print("   ✓ Modal de mapa encontrado")
        if 'google.maps.Map' in content:
            print("   ✓ API de Google Maps incluida")
        else:
            print("   ⚠ API de Google Maps no encontrada en el template")
    else:
        print(f"   ✗ Error: {response.status_code}")
    
    print("\n=== Pruebas completadas ===")

if __name__ == '__main__':
    try:
        test_mejoras()
        sys.exit(0)
    except Exception as e:
        print(f"Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)