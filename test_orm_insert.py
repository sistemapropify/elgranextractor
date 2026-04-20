#!/usr/bin/env python
"""
Test de inserción usando ORM de Django
"""
import os
import sys
import django
import json
import uuid

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceDocument, IntelligenceCollection

def test_orm_insert():
    """Test inserción usando ORM"""
    
    print("Test de inserción usando ORM Django")
    
    # Obtener una colección existente
    try:
        collection = IntelligenceCollection.objects.get(id='491d87ba-5ffe-4d0e-826f-a99d44652181')
        print(f"Colección encontrada: {collection.name}")
    except IntelligenceCollection.DoesNotExist:
        print("ERROR: Colección no encontrada")
        return
    
    # Crear documento usando ORM
    try:
        doc = IntelligenceDocument(
            collection=collection,
            source_id="test_2",
            content="Contenido de prueba",
            metadata_json={"test": 1, "precio": 100000},
            content_hash="test_hash_123"
        )
        
        # No establecer embedding por ahora
        doc.save()
        
        print("OK - Documento creado con ORM")
        print(f"ID generado: {doc.id}")
        print(f"Tipo de ID: {type(doc.id)}")
        print(f"Longitud del ID como string: {len(str(doc.id))}")
        
        # Verificar en base de datos
        from django.db import connections
        conn = connections['default']
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, LEN(id) FROM intelligence_documents WHERE id = %s", (str(doc.id),))
            row = cursor.fetchone()
            if row:
                print(f"En BD - ID: {row[0]}, Longitud: {row[1]}")
        
        # Limpiar
        doc.delete()
        print("Documento eliminado")
        
    except Exception as e:
        print(f"ERROR creando documento: {e}")
        
        # Verificar el error más detalladamente
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_orm_insert()