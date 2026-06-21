#!/usr/bin/env python
"""
Test de inserción directa en intelligence_documents
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

from django.db import connections

def test_direct_insert():
    """Test inserción directa en la tabla real"""
    
    print("Test de inserción directa en intelligence_documents")
    
    # JSON de prueba
    test_json = '{"id": 2, "titulo": "Casa En Campo Verde - Cerro Colorado", "descripcion": "Casa en Campo Verde - Cerro Colorado", "direccion": "Urb. Campo Verde - Cerro Colorado, Arequipa", "distrito": "4", "condicion": "sold", "precio": 299000.0, "moneda": "PEN", "area_construida": null, "area_total": null, "habitaciones": 5, "banos": 4, "estacionamientos": 1, "fecha_creacion": "2026-01-08 02:30:52", "es_propify": 1}'
    
    print(f"JSON de prueba: {test_json[:80]}...")
    
    # Primero verificar ISJSON
    conn = connections['default']
    
    with conn.cursor() as cursor:
        # Verificar ISJSON
        cursor.execute("SELECT ISJSON(%s)", (test_json,))
        isjson_result = cursor.fetchone()[0]
        print(f"ISJSON resultado: {isjson_result}")
        
        if isjson_result != 1:
            print("ERROR: JSON no pasa ISJSON")
            return
        
        # Intentar insertar directamente
        print("\nIntentando inserción directa...")
        
        # Generar valores para los otros campos requeridos
        doc_id = str(uuid.uuid4())
        collection_id = '491d87ba-5ffe-4d0e-826f-a99d44652181'
        content_hash = 'test_hash_' + doc_id[:8]
        embedding = b'test_embedding'
        
        try:
            # Insertar directamente
            cursor.execute("""
                INSERT INTO intelligence_documents 
                (id, collection_id, content_hash, metadata_json, embedding, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, GETDATE(), GETDATE())
            """, (doc_id, collection_id, content_hash, test_json, embedding))
            
            print("OK - Inserción exitosa")
            
            # Limpiar
            cursor.execute("DELETE FROM intelligence_documents WHERE id = %s", (doc_id,))
            print("Registro eliminado")
            
        except Exception as e:
            print(f"ERROR en inserción: {e}")
            
            # Intentar con JSON más simple
            print("\nProbando con JSON más simple...")
            simple_json = '{"test": 1}'
            
            try:
                cursor.execute("SELECT ISJSON(%s)", (simple_json,))
                simple_isjson = cursor.fetchone()[0]
                print(f"ISJSON simple: {simple_isjson}")
                
                cursor.execute("""
                    INSERT INTO intelligence_documents 
                    (id, collection_id, content_hash, metadata_json, embedding, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, GETDATE(), GETDATE())
                """, (doc_id, collection_id, content_hash, simple_json, embedding))
                
                print("OK - JSON simple insertado")
                
                # Limpiar
                cursor.execute("DELETE FROM intelligence_documents WHERE id = %s", (doc_id,))
                
            except Exception as e2:
                print(f"ERROR incluso con JSON simple: {e2}")
                
                # Verificar estructura de la tabla
                print("\nVerificando estructura de la tabla...")
                try:
                    cursor.execute("""
                        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_NAME = 'intelligence_documents'
                        ORDER BY ORDINAL_POSITION
                    """)
                    
                    columns = cursor.fetchall()
                    print("Columnas de intelligence_documents:")
                    for col in columns:
                        print(f"  {col[0]}: {col[1]} (nullable: {col[2]}, max_len: {col[3]})")
                        
                except Exception as e3:
                    print(f"Error obteniendo estructura: {e3}")

if __name__ == "__main__":
    test_direct_insert()