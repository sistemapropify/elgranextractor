#!/usr/bin/env python
"""
Script para probar la sincronización con el método _serialize_row_dict actualizado
"""
import os
import sys
import django
import json

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.services.rag import RAGService
from intelligence.models import IntelligenceCollection, IntelligenceDocument
from django.db import connections

def test_serialization():
    """Probar serialización actualizada"""
    
    print("=== Probando serialización actualizada ===")
    
    try:
        # Obtener conexión a la base de datos propifai
        conn = connections['propifai']
        
        with conn.cursor() as cursor:
            # Ejecutar consulta de la colección
            cursor.execute("""
                SELECT TOP 1
                    p.id,
                    p.title as titulo,
                    p.description as descripcion,
                    p.real_address as direccion,
                    p.district as distrito,
                    p.availability_status as condicion,
                    p.price as precio,
                    'PEN' as moneda,
                    p.built_area as area_construida,
                    p.land_area as area_total,
                    p.bedrooms as habitaciones,
                    p.bathrooms as banos,
                    p.garage_spaces as estacionamientos,
                    p.created_at as fecha_creacion,
                    1 as es_propify
                FROM properties p
                WHERE p.is_active = 1
            """)
            
            columns = [col[0] for col in cursor.description]
            row = cursor.fetchone()
            
            if row:
                row_dict = dict(zip(columns, row))
                print("Datos originales:")
                for key, value in row_dict.items():
                    print(f"  {key}: {repr(value)} ({type(value).__name__})")
                
                # Serializar con método actualizado
                serialized = RAGService._serialize_row_dict(row_dict)
                print("\nDatos serializados:")
                for key, value in serialized.items():
                    print(f"  {key}: {repr(value)} ({type(value).__name__})")
                
                # Convertir a JSON
                json_str = json.dumps(serialized, ensure_ascii=False)
                print(f"\nJSON generado:")
                print(json_str)
                
                # Verificar si podemos insertar un documento de prueba
                print("\n=== Probando inserción en base de datos ===")
                
                # Obtener colección
                collection = IntelligenceCollection.objects.filter(
                    name__icontains='propiedades_propifai',
                    is_active=True
                ).first()
                
                if collection:
                    print(f"Usando colección: {collection.name}")
                    
                    # Generar contenido para embedding
                    content_parts = []
                    embedding_fields = collection.embedding_fields
                    for field in embedding_fields:
                        if field in serialized and serialized[field]:
                            content_parts.append(str(serialized[field]))
                    
                    content = " ".join(content_parts)
                    print(f"Contenido para embedding: {content[:100]}...")
                    
                    # Calcular hash
                    content_hash = RAGService.calculate_content_hash(content)
                    
                    # Generar embedding
                    embedding = RAGService.generate_embedding(content)
                    if embedding:
                        print(f"Embedding generado: {len(embedding)} bytes")
                    else:
                        print("Error generando embedding")
                    
                    # Intentar crear documento
                    try:
                        source_id = str(row_dict.get('id', 'test'))
                        print(f"\nIntentando crear documento con source_id: {source_id}")
                        
                        # Primero eliminar si existe
                        IntelligenceDocument.objects.filter(
                            collection=collection,
                            source_id=source_id
                        ).delete()
                        
                        # Crear nuevo documento
                        doc = IntelligenceDocument.objects.create(
                            collection=collection,
                            source_id=source_id,
                            content=content,
                            content_hash=content_hash,
                            embedding=embedding,
                            metadata_json=json_str
                        )
                        
                        print(f"✅ Documento creado exitosamente!")
                        print(f"  ID: {doc.id}")
                        print(f"  Metadata JSON almacenado: {len(doc.metadata_json)} caracteres")
                        
                        # Verificar que se puede leer
                        try:
                            parsed = json.loads(doc.metadata_json)
                            print(f"  Metadata JSON parseado correctamente")
                        except Exception as e:
                            print(f"  ❌ Error parseando metadata_json: {e}")
                        
                        # Limpiar
                        doc.delete()
                        print(f"  Documento eliminado")
                        
                    except Exception as e:
                        print(f"❌ Error creando documento: {e}")
                        import traceback
                        traceback.print_exc()
                        
                else:
                    print("No se encontró colección")
                    
    except Exception as e:
        print(f"Error general: {e}")
        import traceback
        traceback.print_exc()

def test_full_sync():
    """Probar sincronización completa"""
    
    print("\n\n=== Probando sincronización completa ===")
    
    try:
        # Obtener colección
        collection = IntelligenceCollection.objects.filter(
            name__icontains='propiedades_propifai',
            is_active=True
        ).first()
        
        if collection:
            print(f"Colección: {collection.name} (ID: {collection.id})")
            
            # Limpiar documentos existentes para prueba limpia
            count_before = IntelligenceDocument.objects.filter(collection=collection).count()
            print(f"Documentos existentes: {count_before}")
            
            if count_before > 0:
                print("Eliminando documentos existentes para prueba limpia...")
                IntelligenceDocument.objects.filter(collection=collection).delete()
            
            # Ejecutar sincronización
            print("Ejecutando sincronización...")
            success, message, stats = RAGService.sync_collection(collection.id, force_full_sync=True)
            
            print(f"Resultado:")
            print(f"  Éxito: {success}")
            print(f"  Mensaje: {message}")
            print(f"  Estadísticas: {stats}")
            
            # Verificar documentos creados
            count_after = IntelligenceDocument.objects.filter(collection=collection).count()
            print(f"Documentos después de sincronización: {count_after}")
            
            if count_after > 0:
                print("✅ Sincronización exitosa!")
                # Mostrar un documento de ejemplo
                doc = IntelligenceDocument.objects.filter(collection=collection).first()
                if doc:
                    print(f"\nDocumento de ejemplo:")
                    print(f"  Source ID: {doc.source_id}")
                    print(f"  Content: {doc.content[:100]}...")
                    print(f"  Metadata JSON length: {len(doc.metadata_json)}")
                    
                    # Verificar que metadata_json es JSON válido
                    try:
                        parsed = json.loads(doc.metadata_json)
                        print(f"  Metadata JSON válido (keys: {list(parsed.keys())[:5]}...)")
                    except Exception as e:
                        print(f"  ❌ Metadata JSON inválido: {e}")
            else:
                print("❌ No se crearon documentos")
                
        else:
            print("No se encontró colección")
            
    except Exception as e:
        print(f"Error en sincronización: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_serialization()
    test_full_sync()