#!/usr/bin/env python
"""
Script para probar la creación de colección directamente.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

from intelligence.services.rag import RAGService

def test_create_collection():
    """Prueba la creación de una colección."""
    print("=== Probando creación de colección ===\n")
    
    try:
        # Datos de prueba
        name = "Test Coleccion Properties"
        table_name = "properties"
        embedding_fields = ["title", "description"]
        display_fields = ["code", "title", "price"]
        filter_fields = ["property_type", "district"]
        
        print(f"Parámetros de prueba:")
        print(f"  - name: {name}")
        print(f"  - table_name: {table_name}")
        print(f"  - embedding_fields: {embedding_fields}")
        print(f"  - display_fields: {display_fields}")
        print(f"  - filter_fields: {filter_fields}")
        print(f"  - database_alias: propifai")
        
        # Llamar al método directamente
        print("\nLlamando a RAGService.create_collection_dynamic...")
        success, message, collection = RAGService.create_collection_dynamic(
            name=name,
            table_name=table_name,
            embedding_fields=embedding_fields,
            display_fields=display_fields,
            filter_fields=filter_fields,
            access_level=2,
            description="Colección de prueba para propiedades",
            schema="dbo",
            database_alias="propifai"
        )
        
        print(f"\nResultado:")
        print(f"  - success: {success}")
        print(f"  - message: {message}")
        
        if success and collection:
            print(f"  - collection_id: {collection.id}")
            print(f"  - collection_name: {collection.name}")
            print(f"  - table_name: {collection.table_name}")
            print(f"  - embedding_fields: {collection.embedding_fields}")
            
            # Limpiar: eliminar la colección de prueba
            print("\nLimpiando colección de prueba...")
            collection.delete()
            print("Colección eliminada.")
        else:
            print(f"  - collection: {collection}")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_create_collection()