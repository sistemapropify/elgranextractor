#!/usr/bin/env python
"""
Script simplificado para probar la creación de colección RAG con sincronización automática.
"""

import os
import sys
import django
import json

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument
from intelligence.services.rag import RAGService

def verificar_coleccion_existente():
    """Verifica la colección que el usuario ya creó."""
    print("\n=== VERIFICACION DE COLECCION EXISTENTE ===")
    
    try:
        # Buscar la colección que el usuario mencionó
        collection = IntelligenceCollection.objects.get(name="propiedades_propify")
        
        print(f"COLECCION ENCONTRADA:")
        print(f"   ID: {collection.id}")
        print(f"   Nombre: {collection.name}")
        print(f"   Tabla: {collection.table_name}")
        print(f"   Descripcion: {collection.description}")
        print(f"   Campos embedding: {collection.embedding_fields}")
        print(f"   Campos display: {collection.display_fields}")
        print(f"   Campos filtro: {collection.filter_fields}")
        
        # Contar documentos
        doc_count = IntelligenceDocument.objects.filter(collection=collection).count()
        print(f"   Documentos actuales: {doc_count}")
        
        if doc_count == 0:
            print(f"\nADVERTENCIA: La coleccion existe pero no tiene documentos sincronizados.")
            print(f"   Posibles causas:")
            print(f"   1. La sincronizacion automatica fallo")
            print(f"   2. La tabla 'properties' esta vacia")
            print(f"   3. Hubo un error en el proceso de sincronizacion")
            
        return collection, doc_count
            
    except IntelligenceCollection.DoesNotExist:
        print(f"ERROR: Coleccion 'propiedades_propify' no encontrada")
        return None, 0
    except Exception as e:
        print(f"ERROR al verificar coleccion: {e}")
        return None, 0

def sincronizar_coleccion_manual():
    """Intenta sincronizar manualmente la coleccion existente."""
    print("\n=== SINCRONIZACION MANUAL DE COLECCION ===")
    
    try:
        # Buscar la coleccion
        collection = IntelligenceCollection.objects.get(name="propiedades_propify")
        
        print(f"Sincronizando coleccion: {collection.name} (ID: {collection.id})")
        
        success, message = RAGService.sync_collection_dynamic(
            collection_name=collection.name,
            database_alias='propifai'
        )
        
        print(f"Resultado sincronizacion: {'EXITOSA' if success else 'FALLIDA'}")
        print(f"Mensaje: {message}")
        
        # Verificar documentos despues de sincronizar
        doc_count = IntelligenceDocument.objects.filter(collection=collection).count()
        print(f"Documentos despues de sincronizar: {doc_count}")
        
        return success, doc_count
        
    except IntelligenceCollection.DoesNotExist:
        print(f"ERROR: Coleccion no encontrada")
        return False, 0
    except Exception as e:
        print(f"ERROR en sincronizacion manual: {e}")
        import traceback
        traceback.print_exc()
        return False, 0

def crear_coleccion_prueba():
    """Crea una coleccion de prueba para verificar el funcionamiento."""
    print("\n=== CREACION DE COLECCION DE PRUEBA ===")
    
    try:
        success, message, collection = RAGService.create_collection_dynamic(
            name="propiedades_test_sync",
            table_name="properties",
            embedding_fields=["title", "description"],
            display_fields=["code", "title", "price"],
            filter_fields=["district"],
            access_level=2,
            description="Coleccion de prueba con sincronizacion automatica",
            schema="dbo",
            database_alias="propifai"
        )
        
        if success:
            print(f"COLECCION CREADA EXITOSAMENTE:")
            print(f"   ID: {collection.id}")
            print(f"   Nombre: {collection.name}")
            print(f"   Tabla: {collection.table_name}")
            
            # Intentar sincronizar
            print(f"\nIntentando sincronizar automaticamente...")
            sync_success, sync_message = RAGService.sync_collection_dynamic(
                collection_name=collection.name,
                database_alias='propifai'
            )
            
            print(f"Resultado sincronizacion: {'EXITOSA' if sync_success else 'FALLIDA'}")
            print(f"Mensaje: {sync_message}")
            
            # Verificar documentos
            doc_count = IntelligenceDocument.objects.filter(collection=collection).count()
            print(f"Documentos sincronizados: {doc_count}")
            
            return collection, doc_count
        else:
            print(f"ERROR al crear coleccion: {message}")
            return None, 0
            
    except Exception as e:
        print(f"ERROR en creacion de coleccion: {e}")
        import traceback
        traceback.print_exc()
        return None, 0

if __name__ == "__main__":
    print("Script de prueba para creacion de coleccion RAG con sincronizacion automatica")
    print("=" * 80)
    
    # Verificar coleccion existente
    collection, doc_count = verificar_coleccion_existente()
    
    if collection and doc_count == 0:
        print("\nLa coleccion existe pero no tiene documentos.")
        respuesta = input("¿Desea intentar sincronizar manualmente? (s/n): ")
        if respuesta.lower() == 's':
            sincronizar_coleccion_manual()
    
    print("\n" + "=" * 80)
    print("Prueba completada. Revise los logs del servidor para mas detalles.")