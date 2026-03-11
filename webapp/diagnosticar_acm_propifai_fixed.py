#!/usr/bin/env python
"""
Script para diagnosticar por qué no se ven los marcadores de Propifai en ACM.
Versión corregida para problemas de path.
"""
import os
import sys

# Cambiar al directorio actual (webapp)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Agregar directorio padre al path para importar webapp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    import django
    django.setup()
    print("✓ Django configurado correctamente")
except Exception as e:
    print(f"✗ Error configurando Django: {e}")
    print(f"  Python path: {sys.path}")
    sys.exit(1)

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
        else:
            print("⚠️ No hay propiedades de Propifai con coordenadas")
            
    except Exception as e:
        print(f"✗ Error con modelo PropifaiProperty: {e}")
    
    # 2. Verificar mapeo de ubicaciones
    try:
        from propifai.mapeo_ubicaciones import DEPARTAMENTOS, PROVINCIAS, DISTRITOS
        print(f"✓ Mapeo de ubicaciones cargado: {len(DEPARTAMENTOS)} departamentos, {len(PROVINCIAS)} provincias, {len(DISTRITOS)} distritos")
    except Exception as e:
        print(f"✗ Error con mapeo de ubicaciones: {e}")
    
    # 3. Verificar conexión a base de datos Propifai
    print("\n=== VERIFICANDO CONEXIÓN A BASE DE DATOS PROPIFAI ===")
    try:
        from django.db import connections
        conn = connections['propifai']
        
        # Intentar conectar
        try:
            conn.ensure_connection()
            print("✓ Conexión a base de datos 'propifai' establecida")
        except Exception as e:
            print(f"✗ No se pudo conectar a base de datos 'propifai': {e}")
            print("  Verificar configuración en settings.py")
            return
        
        # Ejecutar consulta simple
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM properties")
            count = cursor.fetchone()[0]
            print(f"✓ Total de propiedades en tabla 'properties': {count}")
            
            # Verificar si hay coordenadas
            cursor.execute("SELECT COUNT(*) FROM properties WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
            count_coords = cursor.fetchone()[0]
            print(f"✓ Propiedades con coordenadas: {count_coords}")
            
            if count_coords == 0:
                print("⚠️ ADVERTENCIA: No hay propiedades con coordenadas en la base de datos Propifai")
                print("  Los marcadores no aparecerán porque no tienen ubicación en el mapa")
                
            # Mostrar algunas propiedades con coordenadas
            if count_coords > 0:
                cursor.execute("SELECT TOP 3 id, property_type, latitude, longitude FROM properties WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
                rows = cursor.fetchall()
                print("  Ejemplos de propiedades con coordenadas:")
                for row in rows:
                    print(f"    ID={row[0]}, tipo={row[1]}, lat={row[2]}, lng={row[3]}")
                    
    except Exception as e:
        print(f"✗ Error con base de datos Propifai: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. Verificar vista ACM directamente
    print("\n=== VERIFICANDO VISTA ACM ===")
    try:
        from acm.views import buscar_comparables
        print("✓ Vista buscar_comparables importada correctamente")
        
        # Verificar el código de la vista
        import inspect
        source = inspect.getsource(buscar_comparables)
        if 'propiedades_propifai' in source:
            print("✓ La vista incluye lógica para propiedades de Propifai")
        else:
            print("⚠️ La vista NO parece incluir lógica para propiedades de Propifai")
            
    except Exception as e:
        print(f"✗ Error importando vista ACM: {e}")
    
    # 5. Verificar si hay propiedades cerca de Arequipa
    print("\n=== BUSCANDO PROPIEDADES CERCA DE AREQUIPA ===")
    try:
        from propifai.models import PropifaiProperty
        
        # Buscar propiedades cerca de Arequipa (-16.4090, -71.5375)
        # Radio amplio: 0.1 grados (~11 km)
        props_cerca = PropifaiProperty.objects.using('propifai').filter(
            latitude__gte=-16.5090,
            latitude__lte=-16.3090,
            longitude__gte=-71.6375,
            longitude__lte=-71.4375
        ).exclude(
            latitude__isnull=True
        ).exclude(
            longitude__isnull=True
        )[:5]
        
        count_cerca = props_cerca.count()
        print(f"✓ Propiedades cerca de Arequipa (-16.4090, -71.5375): {count_cerca}")
        
        if count_cerca == 0:
            print("⚠️ No hay propiedades de Propifai cerca de Arequipa")
            print("  Los marcadores no aparecerán si no hay propiedades en el área de búsqueda")
            print("  Sugerencia: Ampliar el radio de búsqueda en ACM o verificar ubicación de propiedades")
            
    except Exception as e:
        print(f"✗ Error buscando propiedades cerca de Arequipa: {e}")

if __name__ == '__main__':
    diagnosticar_propifai_en_acm()