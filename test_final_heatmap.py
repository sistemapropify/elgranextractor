#!/usr/bin/env python
"""
Script final para verificar que el heatmap muestra todas las propiedades correctamente.
"""
import os
import sys
import django
import json

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from market_analysis.views import heatmap_view
from django.test import RequestFactory

def test_final_heatmap():
    print("=== PRUEBA FINAL DEL HEATMAP ===")
    
    # Crear una request simulada
    factory = RequestFactory()
    request = factory.get('/market-analysis/heatmap/')
    
    # Llamar a la vista
    response = heatmap_view(request)
    
    print(f"Status code: {response.status_code}")
    
    # Verificar contexto
    if hasattr(response, 'context_data'):
        context = response.context_data
        print(f"\n=== DATOS DEL HEATMAP ===")
        print(f"Total propiedades: {context.get('total_count', 'N/A')}")
        print(f"Propiedades locales (Remax): {context.get('local_count', 'N/A')}")
        print(f"Propiedades Propifai: {context.get('propifai_count', 'N/A')}")
        
        heatmap_points = context.get('heatmap_points', [])
        print(f"Número de puntos en heatmap: {len(heatmap_points)}")
        
        if heatmap_points:
            # Analizar distribución de pesos
            weights = [p.get('weight', 0.5) for p in heatmap_points]
            min_weight = min(weights)
            max_weight = max(weights)
            avg_weight = sum(weights) / len(weights)
            
            print(f"\n=== DISTRIBUCIÓN DE PESOS ===")
            print(f"Peso mínimo: {min_weight:.2f}")
            print(f"Peso máximo: {max_weight:.2f}")
            print(f"Peso promedio: {avg_weight:.2f}")
            
            # Contar propiedades por rango de peso
            low = sum(1 for w in weights if w < 1.5)
            medium = sum(1 for w in weights if 1.5 <= w < 2.5)
            high = sum(1 for w in weights if w >= 2.5)
            
            print(f"Propiedades con peso bajo (<1.5): {low}")
            print(f"Propiedades con peso medio (1.5-2.5): {medium}")
            print(f"Propiedades con peso alto (>=2.5): {high}")
            
            # Verificar coordenadas
            print(f"\n=== COORDENADAS ===")
            latitudes = [p['lat'] for p in heatmap_points if 'lat' in p]
            longitudes = [p['lng'] for p in heatmap_points if 'lng' in p]
            
            if latitudes and longitudes:
                min_lat = min(latitudes)
                max_lat = max(latitudes)
                min_lng = min(longitudes)
                max_lng = max(longitudes)
                center_lat = (min_lat + max_lat) / 2
                center_lng = (min_lng + max_lng) / 2
                
                print(f"Latitud mínima: {min_lat:.6f}")
                print(f"Latitud máxima: {max_lat:.6f}")
                print(f"Longitud mínima: {min_lng:.6f}")
                print(f"Longitud máxima: {max_lng:.6f}")
                print(f"Centro calculado: ({center_lat:.6f}, {center_lng:.6f})")
                
                # Verificar que estén en Arequipa
                if min_lat > -17 and max_lat < -16:
                    print("✓ Propiedades en AREQUIPA (correcto)")
                else:
                    print("✗ Propiedades NO están en Arequipa")
            
            # Verificar JSON
            heatmap_data_json = context.get('heatmap_data_json', '')
            print(f"\n=== DATOS JSON ===")
            print(f"Longitud del JSON: {len(heatmap_data_json):,} caracteres")
            
            try:
                parsed = json.loads(heatmap_data_json)
                print(f"JSON parseado correctamente, {len(parsed)} elementos")
                
                # Verificar que todos los elementos tengan lat/lng
                valid_points = sum(1 for p in parsed if 'lat' in p and 'lng' in p)
                print(f"Puntos con coordenadas válidas: {valid_points}/{len(parsed)}")
                
            except json.JSONDecodeError as e:
                print(f"ERROR en JSON: {e}")
    
    # Verificar contenido HTML
    content = response.content.decode('utf-8')
    
    print(f"\n=== VERIFICACIÓN DE FUNCIONALIDAD ===")
    
    # Verificar que se crean marcadores para todas las propiedades
    if 'createMarkers' in content:
        print("✓ Función createMarkers presente")
    else:
        print("✗ Función createMarkers no encontrada")
    
    # Verificar que se pasa heatmap_data_json
    if 'heatmap_data_json' in content:
        print("✓ Datos del heatmap presentes en template")
    else:
        print("✗ Datos del heatmap no encontrados")
    
    # Verificar controles de marcadores
    if 'toggleMarkers' in content:
        print("✓ Control para mostrar/ocultar marcadores presente")
    else:
        print("✗ Control de marcadores no encontrado")
    
    print(f"\n=== RESUMEN FINAL ===")
    print("El heatmap ahora debería mostrar:")
    print("1. Todas las 1540+ propiedades de Remax en Arequipa")
    print("2. Marcadores visibles para cada propiedad (círculos de colores)")
    print("3. Heatmap de densidad superpuesto (opcional)")
    print("4. Navbar y sidebar funcionales")
    print("5. Mapa centrado automáticamente en Arequipa")
    print("6. Info windows con detalles al hacer clic en marcadores")

if __name__ == '__main__':
    test_final_heatmap()