#!/usr/bin/env python
"""
Script final para sincronizar la coleccion reconfigurada.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument
from intelligence.services.rag import RAGService

def verificar_coleccion():
    """Verifica el estado actual de la coleccion."""
    print("=== VERIFICACION DE COLECCION ===")
    
    try:
        collection = IntelligenceCollection.objects.get(name="propiedades_propify")
        
        print(f"Coleccion: {collection.name} (ID: {collection.id})")
        print(f"Tabla: {collection.table_name}")
        print(f"Configuracion actual:")
        print(f"  - Embedding fields: {collection.embedding_fields}")
        print(f"  - Display fields: {collection.display_fields}")
        print(f"  - Filter fields: {collection.filter_fields}")
        
        doc_count = IntelligenceDocument.objects.filter(collection=collection).count()
        print(f"Documentos actuales: {doc_count}")
        
        return collection, doc_count
        
    except IntelligenceCollection.DoesNotExist:
        print(f"ERROR: Coleccion 'propiedades_propify' no encontrada")
        return None, 0
    except Exception as e:
        print(f"ERROR al verificar coleccion: {e}")
        return None, 0

def sincronizar_coleccion():
    """Sincroniza la coleccion."""
    print("\n=== SINCRONIZACION DE COLECCION ===")
    
    try:
        collection = IntelligenceCollection.objects.get(name="propiedades_propify")
        
        print(f"Sincronizando coleccion: {collection.name}")
        
        # Llamar al metodo correcto sin database_alias
        success, message, stats = RAGService.sync_collection_dynamic(
            collection_name=collection.name,
            force_full_sync=True
        )
        
        print(f"Resultado: {'EXITOSA' if success else 'FALLIDA'}")
        print(f"Mensaje: {message}")
        print(f"Estadisticas: {stats}")
        
        # Verificar documentos despues de sincronizar
        doc_count = IntelligenceDocument.objects.filter(collection=collection).count()
        print(f"Documentos sincronizados: {doc_count}")
        
        return success, doc_count, stats
        
    except Exception as e:
        print(f"ERROR en sincronizacion: {e}")
        import traceback
        traceback.print_exc()
        return False, 0, {}

def verificar_conexion():
    """Verifica que la conexion a la base de datos propifai funcione."""
    print("\n=== VERIFICACION DE CONEXION ===")
    
    try:
        from django.db import connections
        
        # Probar conexion a propifai
        with connections['propifai'].cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM [dbo].[properties]")
            row_count = cursor.fetchone()[0]
            print(f"Conexion a 'propifai': OK")
            print(f"Registros en tabla 'properties': {row_count}")
            
            if row_count > 0:
                cursor.execute("SELECT TOP 1 id, code, title FROM [dbo].[properties]")
                row = cursor.fetchone()
                print(f"Ejemplo registro: ID={row[0]}, Codigo={row[1]}, Titulo={row[2]}")
            
            return True, row_count
            
    except Exception as e:
        print(f"ERROR en conexion a 'propifai': {e}")
        return False, 0

if __name__ == "__main__":
    print("Script de sincronizacion final para coleccion RAG")
    print("=" * 80)
    
    # Verificar conexion
    conexion_ok, row_count = verificar_conexion()
    
    if not conexion_ok or row_count == 0:
        print(f"\nERROR: No se puede sincronizar. Verifique la conexion a la base de datos.")
        sys.exit(1)
    
    # Verificar coleccion
    collection, doc_count = verificar_coleccion()
    
    if not collection:
        print(f"\nERROR: Coleccion no encontrada.")
        sys.exit(1)
    
    print(f"\nLa coleccion tiene {doc_count} documentos. ¿Desea sincronizar?")
    print("(Esto importara los 83 registros de la tabla 'properties')")
    
    # Sincronizar
    success, new_doc_count, stats = sincronizar_coleccion()
    
    if success and new_doc_count > 0:
        print(f"\n" + "=" * 80)
        print(f"SINCRONIZACION EXITOSA!")
        print(f"  - Documentos importados: {new_doc_count}")
        print(f"  - Estadisticas: {stats}")
        print(f"  - La coleccion esta lista para busquedas RAG")
        
        # Mostrar resumen
        print(f"\nRESUMEN:")
        print(f"  1. Coleccion: {collection.name}")
        print(f"  2. Tabla: {collection.table_name}")
        print(f"  3. Campos embedding: {len(collection.embedding_fields)} campos")
        print(f"  4. Documentos: {new_doc_count} registros importados")
        print(f"  5. Estado: LISTO PARA USAR")
        
    else:
        print(f"\n" + "=" * 80)
        print(f"SINCRONIZACION FALLIDA")
        print(f"  - Revise los logs del servidor para mas detalles")
        print(f"  - Verifique que la tabla 'properties' tenga datos")
        print(f"  - Verifique que los campos de embedding sean validos")
    
    print(f"\n" + "=" * 80)
    print(f"PASOS SIGUIENTES:")
    print(f"1. Verifique en el admin: http://127.0.0.1:8000/admin/intelligence/intelligencecollection/")
    print(f"2. Pruebe busquedas en: http://127.0.0.1:8000/api/v1/intelligence/rag/search/")
    print(f"3. Use la interfaz web: http://127.0.0.1:8000/api/v1/intelligence/collections/create/")