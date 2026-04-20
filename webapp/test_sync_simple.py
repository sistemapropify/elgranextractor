#!/usr/bin/env python
"""
Script simple para probar la sincronización.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from intelligence.services.rag import RAGService
from intelligence.models import IntelligenceCollection, IntelligenceDocument

def main():
    print("=== Prueba de sincronizacion ===")
    
    collection_id = 'b899d903-5a14-4b23-b567-6bf15aa5f5b9'
    
    try:
        collection = IntelligenceCollection.objects.get(id=collection_id)
        print("Coleccion:", collection.name)
        print("ID:", collection.id)
        
        # Contar documentos actuales
        current_count = IntelligenceDocument.objects.filter(collection=collection).count()
        print("Documentos actuales:", current_count)
        
        # Ejecutar sincronización
        print("\nEjecutando sincronizacion...")
        success, message, stats = RAGService.sync_collection(collection_id)
        
        print("Exito:", success)
        print("Mensaje:", message)
        print("Estadisticas:", stats)
        
        # Contar documentos después
        new_count = IntelligenceDocument.objects.filter(collection=collection).count()
        print("\nDocumentos despues de sincronizacion:", new_count)
        
        if success:
            print("\nOK - Sincronizacion exitosa")
            if new_count > current_count:
                print("   Se agregaron", new_count - current_count, "nuevos documentos")
            
            # Mostrar algunos documentos
            if new_count > 0:
                print("\nMuestra de documentos:")
                docs = IntelligenceDocument.objects.filter(collection=collection)[:3]
                for i, doc in enumerate(docs):
                    print(f"  {i+1}. ID: {doc.source_id}, Contenido: {doc.content[:50]}...")
        else:
            print("\nERROR - Sincronizacion fallo")
            
    except Exception as e:
        print("Error:", str(e))
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()