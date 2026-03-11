#!/usr/bin/env python
"""
Script simple para diagnosticar por qué no se ven los marcadores de Propifai en ACM.
Sin caracteres Unicode para evitar problemas en Windows.
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
    print("OK - Django configurado correctamente")
except Exception as e:
    print(f"ERROR - Configurando Django: {e}")
    print(f"  Python path: {sys.path}")
    sys.exit(1)

def diagnosticar_propifai_en_acm():
    """Diagnosticar por qué no se ven propiedades de Propifai en ACM."""
    print("=== DIAGNOSTICO ACM PROPIFAI ===")
    
    # 1. Verificar si el modelo PropifaiProperty está disponible
    try:
        from propifai.models import PropifaiProperty
        print("OK - Modelo PropifaiProperty importado correctamente")
        
        # Contar propiedades con coordenadas
        count = PropifaiProperty.objects.using('propifai').exclude(
            latitude__isnull=True
        ).exclude(
            longitude__isnull=True
        ).count()
        print(f"OK - Propiedades de Propifai con coordenadas: {count}")
        
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
            print("ADVERTENCIA - No hay propiedades de Propifai con coordenadas")
            
    except Exception as e:
        print(f"ERROR - Con modelo PropifaiProperty: {e}")
    
    # 2. Verificar conexión a base de datos Propifai
    print("\n=== VERIFICANDO CONEXION A BASE DE DATOS PROPIFAI ===")
    try:
        from django.db import connections
        conn = connections['propifai']
        
        # Intentar conectar
        try:
            conn.ensure_connection()
            print("OK - Conexion a base de datos 'propifai' establecida")
        except Exception as e:
            print(f"ERROR - No se pudo conectar a base de datos 'propifai': {e}")
            print("  Verificar configuracion en settings.py")
            return
        
        # Ejecutar consulta simple
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM properties")
            count = cursor.fetchone()[0]
            print(f"OK - Total de propiedades en tabla 'properties': {count}")
            
            # Verificar si hay coordenadas
            cursor.execute("SELECT COUNT(*) FROM properties WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
            count_coords = cursor.fetchone()[0]
            print(f"OK - Propiedades con coordenadas: {count_coords}")
            
            if count_coords == 0:
                print("ADVERTENCIA - No hay propiedades con coordenadas en la base de datos Propifai")
                print("  Los marcadores no apareceran porque no tienen ubicacion en el mapa")
                
            # Mostrar algunas propiedades con coordenadas
            if count_coords > 0:
                cursor.execute("SELECT TOP 3 id, property_type, latitude, longitude FROM properties WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
                rows = cursor.fetchall()
                print("  Ejemplos de propiedades con coordenadas:")
                for row in rows:
                    print(f"    ID={row[0]}, tipo={row[1]}, lat={row[2]}, lng={row[3]}")
                    
    except Exception as e:
        print(f"ERROR - Con base de datos Propifai: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Verificar si hay propiedades cerca de Arequipa
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
        print(f"OK - Propiedades cerca de Arequipa (-16.4090, -71.5375): {count_cerca}")
        
        if count_cerca == 0:
            print("ADVERTENCIA - No hay propiedades de Propifai cerca de Arequipa")
            print("  Los marcadores no apareceran si no hay propiedades en el area de busqueda")
            print("  Sugerencia: Ampliar el radio de busqueda en ACM o verificar ubicacion de propiedades")
            
    except Exception as e:
        print(f"ERROR - Buscando propiedades cerca de Arequipa: {e}")
    
    # 4. Verificar la vista ACM directamente
    print("\n=== VERIFICANDO CODIGO DE LA VISTA ACM ===")
    try:
        # Leer el archivo de la vista directamente
        vista_path = os.path.join(os.path.dirname(__file__), 'acm', 'views.py')
        if os.path.exists(vista_path):
            with open(vista_path, 'r', encoding='utf-8') as f:
                contenido = f.read()
                
            # Buscar indicadores clave
            if 'PropifaiProperty' in contenido:
                print("OK - La vista ACM hace referencia a PropifaiProperty")
            else:
                print("ADVERTENCIA - La vista ACM NO hace referencia a PropifaiProperty")
                
            if 'propiedades_propifai' in contenido:
                print("OK - La vista incluye variable propiedades_propifai")
            else:
                print("ADVERTENCIA - La vista NO incluye variable propiedades_propifai")
                
            if 'es_propify' in contenido:
                print("OK - La vista incluye campo es_propify")
            else:
                print("ADVERTENCIA - La vista NO incluye campo es_propify")
        else:
            print(f"ERROR - No se encontro el archivo de vista: {vista_path}")
            
    except Exception as e:
        print(f"ERROR - Verificando codigo de vista: {e}")

if __name__ == '__main__':
    diagnosticar_propifai_en_acm()