#!/usr/bin/env python
"""
Test final de sincronización con debug detallado
"""
import os
import sys
import django
import json
import traceback

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.services.rag import RAGService
from intelligence.models import IntelligenceCollection

def test_sync_with_debug():
    """Test sincronización con debug detallado"""
    
    print("Test de sincronización con debug detallado")
    
    # Obtener la colección
    try:
        collection = IntelligenceCollection.objects.get(id='491d87ba-5ffe-4d0e-826f-a99d44652181')
        print(f"Colección: {collection.name}")
        print(f"SQL: {collection.source_sql[:100]}...")
        print(f"Campos embedding: {collection.embedding_fields}")
    except Exception as e:
        print(f"ERROR obteniendo colección: {e}")
        return
    
    # Probar sincronización
    try:
        print("\nIniciando sincronización...")
        success, message = RAGService.sync_collection(collection.id)
        
        print(f"Resultado: {success}")
        print(f"Mensaje: {message}")
        
        if not success:
            print("\nDebug adicional:")
            # Verificar si hay documentos en la colección
            from intelligence.models import IntelligenceDocument
            count = IntelligenceDocument.objects.filter(collection=collection).count()
            print(f"Documentos actuales en colección: {count}")
            
    except Exception as e:
        print(f"ERROR en sincronización: {e}")
        traceback.print_exc()
        
        # Debug adicional: probar la conexión a la base de datos propifai
        print("\nProbando conexión a base de datos propifai...")
        from django.db import connections
        try:
            conn = connections['propifai']
            with conn.cursor() as cursor:
                cursor.execute("SELECT TOP 1 id, titulo FROM properties")
                row = cursor.fetchone()
                print(f"Conexión exitosa. Primer registro: {row}")
        except Exception as e2:
            print(f"ERROR en conexión propifai: {e2}")

if __name__ == "__main__":
    test_sync_with_debug()