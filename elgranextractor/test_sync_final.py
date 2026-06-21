#!/usr/bin/env python
"""
Script para probar la sincronización de la colección propiedades_propifai
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection
from intelligence.services.rag import RAGService

def test_sync():
    """Probar sincronización de colección propiedades_propifai"""
    try:
        # Buscar la colección por nombre
        collection = IntelligenceCollection.objects.filter(
            name__icontains='propiedades_propifai',
            is_active=True
        ).first()
        
        if not collection:
            print("ERROR: No se encontró la colección 'propiedades_propifai'")
            # Buscar cualquier colección activa
            collection = IntelligenceCollection.objects.filter(is_active=True).first()
            if not collection:
                print("ERROR: No hay colecciones activas")
                return
        
        print(f"Probando sincronización de colección: {collection.name} (ID: {collection.id})")
        print(f"SQL: {collection.source_sql[:100]}...")
        print(f"Embedding fields: {collection.embedding_fields}")
        
        # Probar sincronización
        success, message, stats = RAGService.sync_collection(collection.id, force_full_sync=True)
        
        print(f"\nResultado de sincronización:")
        print(f"  Éxito: {success}")
        print(f"  Mensaje: {message}")
        print(f"  Estadísticas: {stats}")
        
        if success:
            print("\n✅ Sincronización exitosa!")
            # Verificar documentos creados
            from intelligence.models import IntelligenceDocument
            doc_count = IntelligenceDocument.objects.filter(collection=collection).count()
            print(f"  Documentos en colección: {doc_count}")
        else:
            print("\n❌ Error en sincronización")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("=== Prueba de sincronización de colección RAG ===")
    test_sync()