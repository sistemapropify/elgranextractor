#!/usr/bin/env python
"""
Script para probar la vista del heatmap y verificar que los datos se pasan correctamente.
"""
import os
import sys
import django
from django.test import RequestFactory

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from market_analysis.views import heatmap_view

def test_heatmap_view():
    print("=== PRUEBA DE VISTA HEATMAP ===")
    
    # Crear una request simulada
    factory = RequestFactory()
    request = factory.get('/market-analysis/heatmap/')
    
    # Llamar a la vista
    response = heatmap_view(request)
    
    print(f"Status code: {response.status_code}")
    print(f"Content type: {response['Content-Type']}")
    
    # Verificar que se usa el template correcto
    if hasattr(response, 'template_name'):
        print(f"Template usado: {response.template_name}")
    
    # Verificar contexto
    if hasattr(response, 'context_data'):
        context = response.context_data
        print(f"\n=== CONTEXTO DE LA VISTA ===")
        print(f"Total propiedades: {context.get('total_count', 'N/A')}")
        print(f"Propiedades locales (Remax): {context.get('local_count', 'N/A')}")
        print(f"Propiedades Propifai: {context.get('propifai_count', 'N/A')}")
        
        heatmap_points = context.get('heatmap_points', [])
        print(f"Número de puntos en heatmap: {len(heatmap_points)}")
        
        if heatmap_points:
            print(f"\n=== EJEMPLO DE PUNTOS (primeros 3) ===")
            for i, point in enumerate(heatmap_points[:3]):
                print(f"{i+1}. Lat: {point.get('lat')}, Lng: {point.get('lng')}, "
                      f"Peso: {point.get('weight')}, Fuente: {point.get('fuente')}")
        
        # Verificar JSON
        heatmap_data_json = context.get('heatmap_data_json', '')
        print(f"\n=== DATOS JSON ===")
        print(f"Longitud del JSON: {len(heatmap_data_json)} caracteres")
        
        # Verificar que el JSON sea válido
        import json
        try:
            parsed = json.loads(heatmap_data_json)
            print(f"JSON parseado correctamente, {len(parsed)} elementos")
        except json.JSONDecodeError as e:
            print(f"ERROR en JSON: {e}")
    
    # Verificar contenido HTML
    content = response.content.decode('utf-8')
    
    # Buscar indicadores clave en el HTML
    print(f"\n=== VERIFICACIÓN HTML ===")
    
    # Verificar que extiende base.html
    if '{% extends' in content or 'extends' in content:
        print("✓ Template extiende base.html")
    else:
        print("✗ No se encontró extends en el template")
    
    # Verificar navbar
    if 'app-header' in content:
        print("✓ Navbar presente (app-header)")
    else:
        print("✗ Navbar no encontrado")
    
    # Verificar sidebar
    if 'app-sidebar' in content:
        print("✓ Sidebar presente (app-sidebar)")
    else:
        print("✗ Sidebar no encontrado")
    
    # Verificar Google Maps
    if 'google.maps' in content or 'google-maps' in content:
        print("✓ Google Maps API referenciada")
    else:
        print("✗ Google Maps no encontrado")
    
    # Verificar heatmap data
    if 'heatmap_data_json' in content:
        print("✓ Datos del heatmap presentes en template")
    else:
        print("✗ Datos del heatmap no encontrados")
    
    print(f"\n=== RESUMEN ===")
    print("La vista del heatmap debería mostrar todas las 1540+ propiedades")
    print("centradas en Arequipa (-16.4, -71.6) con zoom apropiado.")

if __name__ == '__main__':
    test_heatmap_view()