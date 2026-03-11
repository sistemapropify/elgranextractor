#!/usr/bin/env python
"""
Script para diagnosticar por qué no se ven los marcadores de Propifai en ACM.
"""
import os
import sys
import django

# Configurar Django
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

from django.test import RequestFactory
from acm.views import buscar_comparables
import json

def diagnosticar_propifai_en_acm():
    """Diagnosticar por qué no se ven propiedades de Propifai en ACM."""
    print("=== DIAGNÓSTICO ACM PROPIFAI ===")
    
    # 1. Verificar si el modelo PropifaiProperty está disponible
    try:
        from propifai.models import PropifaiProperty
        print("✓ Modelo PropifaiProperty importado correctamente")
        
        # Contar propiedades con coordenadas
        count = PropifaiProperty.objects.using('propifai').exclude(
            latitude__isnull=True
        ).exclude(
            longitude__isnull=True
        ).count()
        print(f"✓ Propiedades de Propifai con coordenadas: {count}")
        
        # Mostrar algunas propiedades de ejemplo
        if count > 0:
            props = PropifaiProperty.objects.using('propifai').exclude(
                latitude__isnull=True
            ).exclude(
                longitude__isnull=True
            )[:3]
            for i, prop in enumerate(props):
                print(f"  Ejemplo {i}: ID={prop.id}, lat={prop.latitude}, lng={prop.longitude}, tipo={prop.property_type}")
    except Exception as e:
        print(f"✗ Error con modelo PropifaiProperty: {e}")
    
    # 2. Verificar mapeo de ubicaciones
    try:
        from propifai.mapeo_ubicaciones import DEPARTAMENTOS, PROVINCIAS, DISTRITOS
        print(f"✓ Mapeo de ubicaciones cargado: {len(DEPARTAMENTOS)} departamentos, {len(PROVINCIAS)} provincias, {len(DISTRITOS)} distritos")
    except Exception as e:
        print(f"✗ Error con mapeo de ubicaciones: {e}")
    
    # 3. Simular una petición a buscar_comparables
    print("\n=== SIMULANDO PETICIÓN A buscar_comparables ===")
    
    factory = RequestFactory()
    data = {
        'lat': -16.4090,
        'lng': -71.5375,
        'radio': 5000,  # 5 km para aumentar probabilidad de encontrar propiedades
        'tipo_propiedad': ''
    }
    
    request = factory.post('/acm/buscar-comparables/', 
                          data=json.dumps(data),
                          content_type='application/json')
    
    try:
        from acm.views import buscar_comparables
        response = buscar_comparables(request)
        
        if response.status_code == 200:
            result = json.loads(response.content)
            print(f"✓ Respuesta exitosa: {result.get('total')} propiedades encontradas")
            
            if result.get('propiedades'):
                locales = 0
                propifai = 0
                
                for i, p in enumerate(result['propiedades'][:10]):  # Mostrar primeras 10
                    fuente = p.get('fuente', 'desconocida')
                    es_propify = p.get('es_propify', False)
                    
                    if fuente == 'propifai' or es_propify:
                        propifai += 1
                        print(f"  PROPIFAI {i}: tipo={p.get('tipo')}, distrito={p.get('distrito')}, lat={p.get('lat')}, lng={p.get('lng')}")
                    else:
                        locales += 1
                        print(f"  LOCAL {i}: tipo={p.get('tipo')}, distrito={p.get('distrito')}, lat={p.get('lat')}, lng={p.get('lng')}")
                
                print(f"\nResumen: {locales} locales, {propifai} Propifai")
                
                if propifai == 0:
                    print("⚠️ ADVERTENCIA: No se encontraron propiedades de Propifai en la respuesta")
                    print("  Posibles causas:")
                    print("  1. No hay propiedades de Propifai en el radio de búsqueda")
                    print("  2. Las propiedades de Propifai no tienen coordenadas válidas")
                    print("  3. Error al conectar con la base de datos Propifai")
                    print("  4. Filtro por tipo de propiedad excluye todas las propiedades")
            else:
                print("⚠️ No se encontraron propiedades en absoluto")
        else:
            print(f"✗ Error en la respuesta: {response.status_code}")
            print(f"  Contenido: {response.content}")
            
    except Exception as e:
        print(f"✗ Error al ejecutar buscar_comparables: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. Verificar conexión a base de datos Propifai
    print("\n=== VERIFICANDO CONEXIÓN A BASE DE DATOS PROPIFAI ===")
    try:
        from django.db import connections
        conn = connections['propifai']
        conn.ensure_connection()
        print("✓ Conexión a base de datos 'propifai' establecida")
        
        # Ejecutar consulta simple
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM properties")
            count = cursor.fetchone()[0]
            print(f"✓ Total de propiedades en tabla 'properties': {count}")
            
            # Verificar si hay coordenadas
            cursor.execute("SELECT COUNT(*) FROM properties WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
            count_coords = cursor.fetchone()[0]
            print(f"✓ Propiedades con coordenadas: {count_coords}")
            
    except Exception as e:
        print(f"✗ Error con base de datos Propifai: {e}")

if __name__ == '__main__':
    diagnosticar_propifai_en_acm()