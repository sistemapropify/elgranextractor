#!/usr/bin/env python
"""
Script para probar la vista de matching masivo.
"""

import os
import sys
import django
from django.test import Client
from django.urls import reverse

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

def test_vista_masivo():
    """Prueba la vista /matching/masivo/."""
    print("=== PRUEBA DE VISTA MATCHING MASIVO ===")
    
    client = Client()
    
    # Obtener la URL
    try:
        response = client.get('/matching/masivo/')
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            content = response.content.decode('utf-8', errors='ignore')
            
            # Verificar elementos clave en la respuesta
            print(f"Tamaño de respuesta: {len(content)} caracteres")
            
            # Buscar indicadores de que la vista funciona
            if 'resumen' in content.lower():
                print("✓ La vista contiene 'resumen'")
            
            # Buscar porcentajes (pueden estar en formato HTML)
            import re
            porcentajes = re.findall(r'(\d+\.?\d*)%', content[:10000])
            if porcentajes:
                print(f"✓ Se encontraron porcentajes en la vista: {set(porcentajes[:5])}")
            else:
                print("✗ No se encontraron porcentajes en la vista")
            
            # Verificar si hay requerimientos listados
            if 'requerimiento' in content.lower():
                print("✓ La vista muestra requerimientos")
            
            # Verificar si hay propiedades cero
            if '0.0%' in content:
                print("⚠️  La vista aún muestra algunos 0.0% (puede ser normal)")
            
            # Extraer un fragmento del HTML para inspección
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'porcentaje' in line.lower() or 'match' in line.lower():
                    print(f"Línea {i}: {line.strip()[:100]}")
                    if i > 10:
                        break
            
        else:
            print(f"✗ Error: Status code {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error al acceder a la vista: {e}")
        import traceback
        traceback.print_exc()

def test_api_matching():
    """Prueba la API de matching."""
    print("\n=== PRUEBA DE API MATCHING ===")
    
    client = Client()
    
    # Probar endpoint de matching para un requerimiento específico
    from requerimientos.models import Requerimiento
    req = Requerimiento.objects.first()
    if req:
        print(f"Probando API para requerimiento ID: {req.id}")
        
        try:
            response = client.get(f'/api/matching/{req.id}/ejecutar/')
            print(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                import json
                data = json.loads(response.content)
                print(f"  Total resultados: {data.get('parametros', {}).get('total_resultados', 0)}")
                print(f"  Mejor score: {data.get('resultados', [{}])[0].get('score_total', 0) if data.get('resultados') else 0}")
            else:
                print(f"  Error: {response.content[:200]}")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == '__main__':
    test_vista_masivo()
    test_api_matching()