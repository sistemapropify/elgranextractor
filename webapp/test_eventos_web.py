#!/usr/bin/env python
"""
Script para probar la funcionalidad web del módulo de eventos.
"""
import sys
import os

# Añadir el directorio padre al path para importar webapp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import Client

def test_dashboard_eventos():
    """Prueba la vista principal del dashboard de eventos."""
    client = Client()
    
    print("=== Prueba del dashboard de eventos ===")
    
    # Prueba 1: Página principal sin filtros
    response = client.get('/eventos/')
    print(f"GET /eventos/ - Status: {response.status_code}")
    if response.status_code == 200:
        print("✓ Página cargada correctamente")
        # Verificar que la respuesta contiene elementos esperados
        content = response.content.decode('utf-8')
        if 'Eventos' in content:
            print("✓ Título 'Eventos' encontrado")
        if 'table' in content:
            print("✓ Tabla de eventos presente")
        if 'Filtrar' in content:
            print("✓ Formulario de filtros presente")
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"Contenido: {response.content[:500]}")
        return False
    
    # Prueba 2: Página con filtro por día
    response = client.get('/eventos/?dia=2024-01-01')
    print(f"\nGET /eventos/?dia=2024-01-01 - Status: {response.status_code}")
    if response.status_code == 200:
        print("✓ Filtro por día funciona")
    else:
        print(f"✗ Error en filtro por día: {response.status_code}")
    
    # Prueba 3: Página con filtro por propiedad
    response = client.get('/eventos/?propiedad=123')
    print(f"\nGET /eventos/?propiedad=123 - Status: {response.status_code}")
    if response.status_code == 200:
        print("✓ Filtro por propiedad funciona")
    else:
        print(f"✗ Error en filtro por propiedad: {response.status_code}")
    
    # Prueba 4: Página con paginación
    response = client.get('/eventos/?page=2')
    print(f"\nGET /eventos/?page=2 - Status: {response.status_code}")
    if response.status_code == 200:
        print("✓ Paginación funciona")
    else:
        print(f"✗ Error en paginación: {response.status_code}")
    
    # Prueba 5: Detalle de evento (usar un ID existente si hay datos)
    from eventos.models import Event
    try:
        evento = Event.objects.first()
        if evento:
            response = client.get(f'/eventos/{evento.id}/')
            print(f"\nGET /eventos/{evento.id}/ - Status: {response.status_code}")
            if response.status_code == 200:
                print("✓ Vista de detalle funciona")
                content = response.content.decode('utf-8')
                if str(evento.id) in content:
                    print("✓ ID del evento encontrado en la página")
            else:
                print(f"✗ Error en vista de detalle: {response.status_code}")
        else:
            print("\n⚠ No hay eventos en la base de datos para probar detalle")
    except Exception as e:
        print(f"\n⚠ Error al probar detalle: {e}")
    
    print("\n=== Pruebas completadas ===")
    return True

if __name__ == '__main__':
    try:
        success = test_dashboard_eventos()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)