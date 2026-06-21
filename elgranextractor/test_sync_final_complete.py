#!/usr/bin/env python
"""
Test final de sincronización completa
"""
import os
import sys
import django
import traceback

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.services.rag import RAGService
from intelligence.models import IntelligenceCollection

def test_sync_complete():
    """Test sincronización completa"""
    
    print("=== TEST FINAL DE SINCRONIZACIÓN ===")
    
    # Obtener la colección
    try:
        collection = IntelligenceCollection.objects.get(id='491d87ba-5ffe-4d0e-826f-a99d44652181')
        print(f"Colección: {collection.name}")
        print(f"ID: {collection.id}")
        print(f"SQL (primeras 200 chars): {collection.source_sql[:200]}...")
        print(f"Campos embedding: {collection.embedding_fields}")
    except Exception as e:
        print(f"ERROR obteniendo colección: {e}")
        return
    
    # Verificar conexión a base de datos
    print("\n=== Verificando conexiones ===")
    from django.db import connections
    try:
        # Verificar conexión default
        conn_default = connections['default']
        with conn_default.cursor() as cursor:
            cursor.execute("SELECT 1")
            print("Conexión 'default': OK")
    except Exception as e:
        print(f"Conexión 'default': ERROR - {e}")
    
    try:
        # Verificar conexión propifai
        conn_propifai = connections['propifai']
        with conn_propifai.cursor() as cursor:
            cursor.execute("SELECT 1")
            print("Conexión 'propifai': OK")
    except Exception as e:
        print(f"Conexión 'propifai': ERROR - {e}")
    
    # Probar método _get_connection_for_collection
    print("\n=== Probando detección de conexión ===")
    try:
        conn = RAGService._get_connection_for_collection(collection)
        print(f"Conexión detectada para colección: {conn}")
    except Exception as e:
        print(f"ERROR en detección de conexión: {e}")
    
    # Probar sincronización
    print("\n=== Ejecutando sincronización ===")
    try:
        success, message, stats = RAGService.sync_collection(collection.id)
        
        print(f"Resultado: {success}")
        print(f"Mensaje: {message}")
        print(f"Estadísticas: {stats}")
        
        if success:
            print("\n✅ SINCRONIZACIÓN EXITOSA")
            print(f"  - Creados: {stats.get('created', 0)}")
            print(f"  - Actualizados: {stats.get('updated', 0)}")
            print(f"  - Saltados: {stats.get('skipped', 0)}")
            print(f"  - Errores: {stats.get('errors', 0)}")
            print(f"  - Total procesados: {stats.get('total_processed', 0)}")
            
            # Verificar documentos en base de datos
            from intelligence.models import IntelligenceDocument
            count = IntelligenceDocument.objects.filter(collection=collection).count()
            print(f"\nDocumentos en colección después de sync: {count}")
        else:
            print("\n❌ SINCRONIZACIÓN FALLIDA")
            
    except Exception as e:
        print(f"ERROR en sincronización: {e}")
        traceback.print_exc()
        
        # Debug adicional
        print("\n=== Debug adicional ===")
        # Verificar si la tabla existe
        try:
            conn = connections['default']
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM ingestas_propiedadraw WHERE activo = 1")
                count = cursor.fetchone()[0]
                print(f"Registros en ingestas_propiedadraw (activo=1): {count}")
        except Exception as e2:
            print(f"Error consultando ingestas_propiedadraw: {e2}")

if __name__ == "__main__":
    test_sync_complete()