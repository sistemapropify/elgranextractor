#!/usr/bin/env python
"""
Script para probar la vista heatmap_view y verificar que no muestra propiedades inventadas.
"""
import os
import sys
import django

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from django.test import RequestFactory
from market_analysis.views import heatmap_view

def test_heatmap_view():
    print("=== PRUEBA DE VISTA HEATMAP (/market-analysis/heatmap/) ===")
    
    rf = RequestFactory()
    request = rf.get('/market-analysis/heatmap/')
    
    try:
        response = heatmap_view(request)
        print(f'Status Code: {response.status_code}')
        
        # Buscar en el contenido si hay datos de prueba
        content = response.content.decode('utf-8', errors='ignore')
        
        # Buscar patrones que indiquen datos inventados
        test_patterns = [
            'test data',
            'mock data',
            'sample data',
            'inventado',
            'fake',
            'zona',
            'ZonaValor',
            'centroide'
        ]
        
        found_patterns = []
        for pattern in test_patterns:
            if pattern.lower() in content.lower():
                found_patterns.append(pattern)
        
        if found_patterns:
            print(f'\n[WARNING] Se encontraron patrones de datos inventados: {found_patterns}')
        else:
            print('\n[OK] No se encontraron patrones de datos inventados en el HTML')
        
        # Contar propiedades en el JSON
        import re
        import json
        
        # Buscar el JSON de heatmap_data
        match = re.search(r'const heatmapDataJson = (\[.*?\]);', content, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                data = json.loads(json_str)
                print(f'\n[OK] Se encontraron {len(data)} propiedades en el JSON')
                if data:
                    print('Primeras 3 propiedades:')
                    for i, prop in enumerate(data[:3]):
                        print(f'  {i+1}. Lat: {prop.get("lat")}, Lng: {prop.get("lng")}, '
                              f'Fuente: {prop.get("fuente")}, Tipo: {prop.get("tipo", "N/A")}')
            except json.JSONDecodeError as e:
                print(f'\n[ERROR] Error decodificando JSON: {e}')
        else:
            print('\n[WARNING] No se encontró heatmapDataJson en el HTML')
        
        # Verificar mensajes de propiedades reales
        if 'DATOS 100% REALES' in content:
            print('\n[OK] El HTML contiene el mensaje "DATOS 100% REALES"')
        else:
            print('\n[WARNING] El HTML NO contiene el mensaje "DATOS 100% REALES"')
            
        if 'SIN PROPIEDADES INVENTADAS' in content:
            print('[OK] El HTML contiene el mensaje "SIN PROPIEDADES INVENTADAS"')
        else:
            print('[WARNING] El HTML NO contiene el mensaje "SIN PROPIEDADES INVENTADAS"')
            
    except Exception as e:
        print(f'\n[ERROR] Error al ejecutar la vista: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_heatmap_view()