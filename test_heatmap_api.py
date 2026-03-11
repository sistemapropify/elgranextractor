#!/usr/bin/env python
"""
Script para probar la API del heatmap y verificar que devuelve propiedades reales.
"""
import os
import sys
import django
import json

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from cuadrantizacion.views import api_heatmap_data

def test_heatmap_api():
    print("=== PRUEBA DE API HEATMAP (PROPIEDADES REALES) ===")
    
    rf = RequestFactory()
    request = rf.get('/api/cuadrantizacion/heatmap-data/')
    
    try:
        response = api_heatmap_data(request)
        print(f'Status Code: {response.status_code}')
        
        if response.status_code == 200:
            data = json.loads(response.content)
            
            print(f'\n[OK] API funciona correctamente')
            print(f'Total propiedades: {data.get("total_propiedades")}')
            print(f'Propiedades Remax: {data.get("total_local")}')
            print(f'Propiedades Propify: {data.get("total_propifai")}')
            print(f'Nota: {data.get("nota")}')
            
            # Verificar que no hay datos inventados
            heatmap_data = data.get('heatmap_data', [])
            print(f'\nPuntos en heatmap: {len(heatmap_data)}')
            
            if heatmap_data:
                print('\nPrimeros 3 puntos:')
                for i, point in enumerate(heatmap_data[:3]):
                    print(f'  {i+1}. Lat: {point.get("lat")}, Lng: {point.get("lng")}, '
                          f'Precio m²: ${point.get("precio_m2", 0):.2f}, '
                          f'Fuente: {point.get("fuente")}, Tipo: {point.get("tipo")}')
            
            # Verificar que no hay zonas inventadas
            has_zones = any('zona' in str(point).lower() for point in heatmap_data)
            if has_zones:
                print('\n[WARNING] ADVERTENCIA: Se detectaron zonas en los datos (posiblemente inventadas)')
            else:
                print('\n[OK] CONFIRMADO: No hay zonas inventadas, solo propiedades reales')
                
        else:
            print(f'\n[ERROR] Error en la API: {response.content}')
            
    except Exception as e:
        print(f'\n[ERROR] Error al ejecutar la API: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_heatmap_api()