#!/usr/bin/env python
"""
Script para probar la creación de colección RAG con sincronización automática.
"""

import os
import sys
import django
import json
import requests

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument

def test_creacion_con_sync():
    """Prueba la creación de colección con sincronización automática."""
    print("=== PRUEBA DE CREACIÓN DE COLECCIÓN CON SINCRONIZACIÓN AUTOMÁTICA ===")
    
    # URL de la API
    url = "http://127.0.0.1:8000/api/v1/intelligence/rag/collections/"
    
    # Datos de prueba
    data = {
        "name": "propiedades_propify_test_sync",
        "table_name": "properties",
        "schema": "dbo",
        "database": "propifai",
        "description": "Colección de prueba con sincronización automática",
        "access_level": 2,
        "embedding_fields": json.dumps(["title", "description", "project_name"]),
        "display_fields": json.dumps(["code", "title", "price", "real_address", "exact_address"]),
        "filter_fields": json.dumps(["district", "garage_type_id", "status_id"])
    }
    
    print(f"Datos enviados: {json.dumps(data, indent=2)}")
    
    try:
        # Enviar solicitud POST
        response = requests.post(url, json=data)
        print(f"\nRespuesta HTTP: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Respuesta JSON: {json.dumps(result, indent=2)}")
            
            if result.get('success'):
                collection_id = result['collection']['id']
                sync_success = result.get('sync_success', False)
                sync_message = result.get('sync_message', '')
                
                print(f"\n✅ Colección creada exitosamente:")
                print(f"   ID: {collection_id}")
                print(f"   Nombre: {result['collection']['name']}")
                print(f"   Tabla: {result['collection']['table_name']}")
                print(f"   Base de datos: propifai")
                print(f"   Sincronización automática: {'✅ Exitosa' if sync_success else '❌ Fallida'}")
                print(f"   Mensaje sincronización: {sync_message}")
                
                # Verificar en la base de datos
                try:
                    collection = IntelligenceCollection.objects.get(id=collection_id)
                    print(f"\n📊 Verificación en base de datos:")
                    print(f"   Colección encontrada: {collection.name}")
                    print(f"   Tabla: {collection.table_name}")
                    print(f"   Campos embedding: {collection.embedding_fields}")
                    print(f"   Campos display: {collection.display_fields}")
                    print(f"   Campos filtro: {collection.filter_fields}")
                    
                    # Contar documentos sincronizados
                    doc_count = IntelligenceDocument.objects.filter(collection=collection).count()
                    print(f"   Documentos sincronizados: {doc_count}")
                    
                    if doc_count > 0:
                        print(f"   ✅ Sincronización exitosa: {doc_count} documentos importados")
                    else:
                        print(f"   ⚠️  Colección creada pero sin documentos sincronizados")
                        
                except IntelligenceCollection.DoesNotExist:
                    print(f"   ❌ Colección no encontrada en la base de datos")
                    
            else:
                print(f"\n❌ Error al crear colección: {result.get('error', 'Error desconocido')}")
        else:
            print(f"\n❌ Error HTTP: {response.status_code}")
            print(f"Respuesta: {response.text}")
            
    except Exception as e:
        print(f"\n❌ Error en la prueba: {e}")
        import traceback
        traceback.print_exc()

def verificar_coleccion_existente():
    """Verifica la colección que el usuario ya creó."""
    print("\n=== VERIFICACIÓN DE COLECCIÓN EXISTENTE ===")
    
    try:
        # Buscar la colección que el usuario mencionó
        collection = IntelligenceCollection.objects.get(name="propiedades_propify")
        
        print(f"✅ Colección encontrada:")
        print(f"   ID: {collection.id}")
        print(f"   Nombre: {collection.name}")
        print(f"   Tabla: {collection.table_name}")
        print(f"   Descripción: {collection.description}")
        print(f"   Campos embedding: {collection.embedding_fields}")
        print(f"   Campos display: {collection.display_fields}")
        print(f"   Campos filtro: {collection.filter_fields}")
        
        # Contar documentos
        doc_count = IntelligenceDocument.objects.filter(collection=collection).count()
        print(f"   Documentos actuales: {doc_count}")
        
        if doc_count == 0:
            print(f"\n⚠️  La colección existe pero no tiene documentos sincronizados.")
            print(f"   Esto puede deberse a:")
            print(f"   1. La sincronización automática falló")
            print(f"   2. La tabla 'properties' está vacía")
            print(f"   3. Hubo un error en el proceso de sincronización")
            
            # Intentar sincronizar manualmente
            print(f"\n💡 Solución: Sincronizar manualmente desde el admin o usar el endpoint de sincronización")
            
    except IntelligenceCollection.DoesNotExist:
        print(f"❌ Colección 'propiedades_propify' no encontrada")
    except Exception as e:
        print(f"❌ Error al verificar colección: {e}")

def sincronizar_coleccion_manual():
    """Intenta sincronizar manualmente la colección existente."""
    print("\n=== SINCRONIZACIÓN MANUAL DE COLECCIÓN ===")
    
    try:
        # Buscar la colección
        collection = IntelligenceCollection.objects.get(name="propiedades_propify")
        
        print(f"Sincronizando colección: {collection.name} (ID: {collection.id})")
        
        # Usar el servicio RAG para sincronizar
        from intelligence.services.rag import RAGService
        
        success, message = RAGService.sync_collection_dynamic(
            collection_name=collection.name,
            database_alias='propifai'
        )
        
        print(f"Resultado sincronización: {'✅ Exitosa' if success else '❌ Fallida'}")
        print(f"Mensaje: {message}")
        
        # Verificar documentos después de sincronizar
        doc_count = IntelligenceDocument.objects.filter(collection=collection).count()
        print(f"Documentos después de sincronizar: {doc_count}")
        
    except IntelligenceCollection.DoesNotExist:
        print(f"❌ Colección no encontrada")
    except Exception as e:
        print(f"❌ Error en sincronización manual: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Script de prueba para creación de colección RAG con sincronización automática")
    print("=" * 80)
    
    # Verificar colección existente primero
    verificar_coleccion_existente()
    
    # Preguntar si quiere probar creación nueva
    print("\n¿Desea probar la creación de una nueva colección con sincronización automática?")
    print("(Esto creará una colección de prueba)")
    
    # Ejecutar prueba de creación
    test_creacion_con_sync()
    
    # Ofrecer sincronización manual
    print("\n¿Desea intentar sincronizar manualmente la colección existente?")
    sincronizar_coleccion_manual()
    
    print("\n" + "=" * 80)
    print("Prueba completada. Revise los logs del servidor para más detalles.")