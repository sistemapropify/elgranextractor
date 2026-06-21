#!/usr/bin/env python
"""
Script para reconfigurar la coleccion existente con campos apropiados y sincronizarla.
Version sin emojis para Windows.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument
from intelligence.services.rag import RAGService

def verificar_tabla_properties():
    """Verifica si la tabla properties tiene datos."""
    print("\n=== VERIFICACION DE TABLA PROPERTIES ===")
    
    try:
        from django.db import connections
        
        # Conectar a la base de datos propifai
        with connections['propifai'].cursor() as cursor:
            # Contar registros
            cursor.execute("SELECT COUNT(*) FROM [dbo].[properties]")
            row_count = cursor.fetchone()[0]
            
            print(f"Registros en tabla 'properties': {row_count}")
            
            # Obtener algunas columnas de ejemplo
            if row_count > 0:
                cursor.execute("SELECT TOP 3 id, code, title, price FROM [dbo].[properties]")
                rows = cursor.fetchall()
                
                print(f"\nEjemplo de registros (primeros 3):")
                for row in rows:
                    print(f"  - ID: {row[0]}, Codigo: {row[1]}, Titulo: {row[2]}, Precio: {row[3]}")
            else:
                print(f"ADVERTENCIA: La tabla 'properties' esta vacia")
                
        return row_count
        
    except Exception as e:
        print(f"ERROR al verificar tabla: {e}")
        import traceback
        traceback.print_exc()
        return 0

def reconfigurar_coleccion():
    """Reconfigura la coleccion existente con campos apropiados."""
    print("\n=== RECONFIGURACION DE COLECCION EXISTENTE ===")
    
    try:
        # Buscar la coleccion existente
        collection = IntelligenceCollection.objects.get(name="propiedades_propify")
        
        print(f"Coleccion encontrada: {collection.name} (ID: {collection.id})")
        print(f"Configuracion actual:")
        print(f"  - Embedding fields: {collection.embedding_fields}")
        print(f"  - Display fields: {collection.display_fields}")
        print(f"  - Filter fields: {collection.filter_fields}")
        
        # Campos recomendados para la tabla 'properties'
        nuevos_embedding = ["title", "description", "project_name", "real_address", "exact_address"]
        nuevos_display = ["code", "title", "price", "real_address", "district", "bedrooms", "bathrooms"]
        nuevos_filter = ["district", "property_type_id", "status_id", "bedrooms", "bathrooms", "price"]
        
        print(f"\nNueva configuracion recomendada:")
        print(f"  - Embedding fields: {nuevos_embedding}")
        print(f"  - Display fields: {nuevos_display}")
        print(f"  - Filter fields: {nuevos_filter}")
        
        # Actualizar la coleccion
        collection.embedding_fields = nuevos_embedding
        collection.display_fields = nuevos_display
        collection.filter_fields = nuevos_filter
        
        collection.save()
        
        print(f"\nCOLECCION RECONFIGURADA EXITOSAMENTE")
        
        return collection
        
    except IntelligenceCollection.DoesNotExist:
        print(f"ERROR: Coleccion 'propiedades_propify' no encontrada")
        return None
    except Exception as e:
        print(f"ERROR al reconfigurar coleccion: {e}")
        import traceback
        traceback.print_exc()
        return None

def sincronizar_coleccion():
    """Sincroniza la coleccion reconfigurada."""
    print("\n=== SINCRONIZACION DE COLECCION ===")
    
    try:
        collection = IntelligenceCollection.objects.get(name="propiedades_propify")
        
        print(f"Sincronizando coleccion: {collection.name}")
        
        # Primero, eliminar documentos existentes (si los hay)
        doc_count_before = IntelligenceDocument.objects.filter(collection=collection).count()
        if doc_count_before > 0:
            print(f"Eliminando {doc_count_before} documentos existentes...")
            IntelligenceDocument.objects.filter(collection=collection).delete()
        
        # Sincronizar con la nueva configuracion
        success, message = RAGService.sync_collection_dynamic(
            collection_name=collection.name,
            database_alias='propifai'
        )
        
        print(f"Resultado sincronizacion: {'EXITOSA' if success else 'FALLIDA'}")
        print(f"Mensaje: {message}")
        
        # Verificar documentos despues de sincronizar
        doc_count_after = IntelligenceDocument.objects.filter(collection=collection).count()
        print(f"Documentos sincronizados: {doc_count_after}")
        
        if doc_count_after > 0:
            print(f"\nSINCRONIZACION EXITOSA! Se importaron {doc_count_after} documentos.")
            
            # Mostrar algunos documentos de ejemplo
            print(f"\nEjemplo de documentos importados (primeros 3):")
            documentos = IntelligenceDocument.objects.filter(collection=collection).order_by('id')[:3]
            for i, doc in enumerate(documentos):
                print(f"  Documento {i+1}:")
                print(f"    ID: {doc.id}")
                print(f"    Source ID: {doc.source_id}")
                print(f"    Contenido (primeros 100 chars): {doc.content[:100]}..." if doc.content else "    Contenido: None")
                print(f"    Embedding: {'SI' if doc.embedding else 'NO'}")
        else:
            print(f"\nADVERTENCIA: La sincronizacion no importo documentos.")
            print(f"   Posibles causas:")
            print(f"   1. La tabla 'properties' esta vacia")
            print(f"   2. Error en la conexion a la base de datos")
            print(f"   3. Problemas con los campos de embedding")
        
        return success, doc_count_after
        
    except IntelligenceCollection.DoesNotExist:
        print(f"ERROR: Coleccion no encontrada")
        return False, 0
    except Exception as e:
        print(f"ERROR en sincronizacion: {e}")
        import traceback
        traceback.print_exc()
        return False, 0

if __name__ == "__main__":
    print("Script para reconfigurar y sincronizar coleccion RAG")
    print("=" * 80)
    
    # Verificar si la tabla tiene datos
    row_count = verificar_tabla_properties()
    
    if row_count == 0:
        print(f"\nERROR: No se puede sincronizar: la tabla 'properties' esta vacia.")
        print(f"   Por favor, asegurese de que la tabla tenga datos antes de continuar.")
        sys.exit(1)
    
    # Reconfigurar coleccion
    collection = reconfigurar_coleccion()
    
    if collection:
        # Sincronizar coleccion
        success, doc_count = sincronizar_coleccion()
        
        if success and doc_count > 0:
            print(f"\n" + "=" * 80)
            print(f"PROCESO COMPLETADO EXITOSAMENTE")
            print(f"   - Coleccion reconfigurada: {collection.name}")
            print(f"   - Documentos importados: {doc_count}")
            print(f"   - La coleccion ahora esta lista para busquedas RAG")
        else:
            print(f"\n" + "=" * 80)
            print(f"PROCESO COMPLETADO CON ADVERTENCIAS")
            print(f"   - La coleccion fue reconfigurada pero no se importaron documentos")
            print(f"   - Revise los logs del servidor para diagnosticar el problema")
    
    print(f"\n" + "=" * 80)
    print(f"INSTRUCCIONES:")
    print(f"1. La coleccion 'propiedades_propify' ha sido reconfigurada")
    print(f"2. Puede verificar en el admin de Django: http://127.0.0.1:8000/admin/")
    print(f"3. Para probar busquedas, use el endpoint: /api/v1/intelligence/rag/search/")
    print(f"4. Los campos de embedding ahora son mas apropiados para busqueda semantica")