#!/usr/bin/env python
"""
Script para probar la funcionalidad de edición del dashboard de calidad de datos.
"""

import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware
from webapp.market_analysis.views import api_update_property_field
from ingestas.models import PropiedadRaw
import json

def test_api_update():
    """Prueba la API de actualización de propiedades."""
    print("=== Prueba de API de actualización de propiedades ===")
    
    # Crear una solicitud POST simulada
    factory = RequestFactory()
    
    # Primero, obtener una propiedad de prueba
    try:
        propiedad = PropiedadRaw.objects.filter(coordenadas__isnull=True).first()
        if not propiedad:
            propiedad = PropiedadRaw.objects.filter(precio_usd__isnull=True).first()
        
        if not propiedad:
            print("No se encontraron propiedades con datos faltantes para probar.")
            # Crear una propiedad de prueba si no hay
            propiedad = PropiedadRaw.objects.first()
            if not propiedad:
                print("No hay propiedades en la base de datos.")
                return
        
        print(f"Propiedad de prueba ID: {propiedad.id}")
        print(f"Coordenadas actuales: {propiedad.coordenadas}")
        print(f"Precio actual: {propiedad.precio_usd}")
        print(f"Área actual: {propiedad.area_construida}")
        
        # Probar actualización de coordenadas
        print("\n1. Probando actualización de coordenadas...")
        request = factory.post('/market-analysis/api/update-property-field/', {
            'id': propiedad.id,
            'field': 'coordenadas',
            'value': '-12.046374, -77.042793'
        })
        
        # Agregar middleware para sesión y autenticación
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        
        auth_middleware = AuthenticationMiddleware(lambda req: None)
        auth_middleware.process_request(request)
        
        response = api_update_property_field(request)
        print(f"   Status code: {response.status_code}")
        print(f"   Response: {response.content.decode()}")
        
        # Verificar si la propiedad se actualizó
        propiedad.refresh_from_db()
        print(f"   Coordenadas después: {propiedad.coordenadas}")
        
        # Probar actualización de precio
        print("\n2. Probando actualización de precio...")
        request = factory.post('/market-analysis/api/update-property-field/', {
            'id': propiedad.id,
            'field': 'precio_usd',
            'value': '150000'
        })
        
        middleware.process_request(request)
        request.session.save()
        
        response = api_update_property_field(request)
        print(f"   Status code: {response.status_code}")
        print(f"   Response: {response.content.decode()}")
        
        propiedad.refresh_from_db()
        print(f"   Precio después: {propiedad.precio_usd}")
        
        # Probar error: precio cero
        print("\n3. Probando error con precio cero...")
        request = factory.post('/market-analysis/api/update-property-field/', {
            'id': propiedad.id,
            'field': 'precio_usd',
            'value': '0'
        })
        
        middleware.process_request(request)
        request.session.save()
        
        response = api_update_property_field(request)
        print(f"   Status code: {response.status_code}")
        print(f"   Response: {response.content.decode()}")
        
        # Probar error: campo no permitido
        print("\n4. Probando error con campo no permitido...")
        request = factory.post('/market-analysis/api/update-property-field/', {
            'id': propiedad.id,
            'field': 'campo_inexistente',
            'value': 'valor'
        })
        
        middleware.process_request(request)
        request.session.save()
        
        response = api_update_property_field(request)
        print(f"   Status code: {response.status_code}")
        print(f"   Response: {response.content.decode()}")
        
        print("\n=== Prueba completada ===")
        
    except Exception as e:
        print(f"Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()

def test_urls():
    """Verifica que las URLs estén configuradas correctamente."""
    print("\n=== Verificación de URLs ===")
    
    try:
        from django.urls import reverse, resolve
        from webapp.market_analysis import urls
        
        # Verificar que la URL existe
        try:
            url = reverse('market_analysis:api_update_property_field')
            print(f"URL encontrada: {url}")
        except Exception as e:
            print(f"Error al obtener URL: {e}")
            print("Asegúrate de que la URL esté registrada en webapp/market_analysis/urls.py")
            
        # Verificar resolución
        try:
            match = resolve('/market-analysis/api/update-property-field/')
            print(f"Resolución exitosa: {match.view_name}")
            print(f"Función: {match.func.__name__ if hasattr(match.func, '__name__') else match.func}")
        except Exception as e:
            print(f"Error en resolución: {e}")
            
    except Exception as e:
        print(f"Error en verificación de URLs: {e}")

def test_template_changes():
    """Verifica que el template tenga los cambios necesarios."""
    print("\n=== Verificación de template ===")
    
    template_path = 'webapp/templates/market_analysis/data_quality_dashboard_fixed.html'
    
    if os.path.exists(template_path):
        print(f"Template encontrado: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Verificar elementos clave
        checks = [
            ('Modal de detalles', 'propertyDetailsModal' in content),
            ('Botones de ver detalles', 'view-details-btn' in content),
            ('Formularios de edición', 'edit-form' in content),
            ('JavaScript para manejo', 'updatePropertyField' in content),
            ('API endpoint', '/market-analysis/api/update-property-field/' in content),
        ]
        
        for name, found in checks:
            status = "✓" if found else "✗"
            print(f"  {status} {name}")
            
        if all(found for _, found in checks):
            print("  Todos los elementos necesarios están presentes.")
        else:
            print("  Algunos elementos faltan.")
    else:
        print(f"Template no encontrado: {template_path}")

if __name__ == '__main__':
    print("Iniciando pruebas de funcionalidad de edición...")
    test_urls()
    test_template_changes()
    test_api_update()
    print("\nPruebas completadas.")