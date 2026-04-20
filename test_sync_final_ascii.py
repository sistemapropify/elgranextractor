#!/usr/bin/env python
"""
Test final de sincronización (solo ASCII)
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

def test_sync_final():
    """Test sincronización final"""
    
    print("=== TEST FINAL DE SINCRONIZACION ===")
    
    # Obtener la colección
    try:
        collection = IntelligenceCollection.objects.get(id='491d87ba-5ffe-4d0e-826f-a99d44652181')
        print(f"Coleccion: {collection.name}")
        print(f"ID: {collection.id}")
        print(f"SQL (primeras 150 chars): {collection.source_sql[:150]}...")
        print(f"Campos embedding: {collection.embedding_fields}")
    except Exception as e:
        print(f"ERROR obteniendo coleccion: {e}")
        return
    
    # Probar sincronización
    print("\n=== Ejecutando sincronizacion ===")
    try:
        success, message, stats = RAGService.sync_collection(collection.id)
        
        print(f"Resultado: {success}")
        print(f"Mensaje: {message}")
        print(f"Estadisticas: {stats}")
        
        if success:
            print("\nSINCRONIZACION EXITOSA")
            print(f"  - Creados: {stats.get('created', 0)}")
            print(f"  - Actualizados: {stats.get('updated', 0)}")
            print(f"  - Saltados: {stats.get('skipped', 0)}")
            print(f"  - Errores: {stats.get('errors', 0)}")
            print(f"  - Total procesados: {stats.get('total_processed', 0)}")
            
            # Verificar documentos en base de datos
            from intelligence.models import IntelligenceDocument
            count = IntelligenceDocument.objects.filter(collection=collection).count()
            print(f"\nDocumentos en coleccion despues de sync: {count}")
            
            # Mostrar algunos documentos
            if count > 0:
                print("\nPrimeros 3 documentos:")
                docs = IntelligenceDocument.objects.filter(collection=collection)[:3]
                for doc in docs:
                    print(f"  - ID: {doc.id}, Source: {doc.source_id}, Hash: {doc.content_hash[:10]}...")
        else:
            print("\nSINCRONIZACION FALLIDA")
            
    except Exception as e:
        print(f"ERROR en sincronizacion: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_sync_final()