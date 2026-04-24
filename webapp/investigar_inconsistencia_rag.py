#!/usr/bin/env python
"""
Script para investigar la inconsistencia del sistema RAG:
- Primero dice que no hay propiedades en Cerro Colorado
- Luego muestra una lista que incluye una propiedad en Cerro Colorado
"""

import os
import sys
import django
import json

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceDocument, IntelligenceCollection
from django.db.models import Q

def investigar_inconsistencia():
    print("=== INVESTIGANDO INCONSISTENCIA DEL SISTEMA RAG ===")
    print()
    
    # 1. Verificar colección propiedades_propify
    print("1. VERIFICANDO COLECCION 'propiedades_propify'")
    try:
        collection = IntelligenceCollection.objects.get(name='propiedades_propify')
        print(f"   [OK] Coleccion encontrada: {collection.name}")
        print(f"   - Tabla: {collection.table_name}")
        print(f"   - Documentos totales: {collection.documents.count()}")
    except IntelligenceCollection.DoesNotExist:
        print("   [ERROR] Coleccion 'propiedades_propify' no encontrada")
        return
    
    print()
    
    # 2. Buscar propiedades en Cerro Colorado por texto
    print("2. BUSCANDO PROPIEDADES EN CERRO COLORADO (BUSQUEDA DE TEXTO)")
    docs_cerro_colorado = IntelligenceDocument.objects.filter(
        collection=collection,
        content__icontains='cerro colorado'
    ).select_related('collection')
    
    print(f"   Documentos encontrados con 'cerro colorado' en contenido: {docs_cerro_colorado.count()}")
    
    for doc in docs_cerro_colorado[:5]:
        print(f"   - ID: {doc.id}, Source ID: {doc.source_id}")
        try:
            data = json.loads(doc.content)
            print(f"     Titulo: {data.get('title', 'Sin titulo')}")
            print(f"     Distrito: {data.get('district', 'Sin distrito')}")
            print(f"     Direccion: {data.get('real_address', 'Sin direccion')}")
            print(f"     Embedding: {'Si' if doc.has_embedding else 'No'}")
        except Exception as e:
            print(f"     Error parseando JSON: {e}")
            print(f"     Contenido (primeros 200 chars): {doc.content[:200]}...")
        print()
    
    print()
    
    # 3. Buscar por distrito 8 (Cerro Colorado)
    print("3. BUSCANDO POR DISTRITO 8 (CERRO COLORADO)")
    all_docs = IntelligenceDocument.objects.filter(collection=collection)
    docs_distrito_8 = []
    
    for doc in all_docs:
        try:
            data = json.loads(doc.content)
            district = data.get('district')
            if district == '8' or district == 8:
                docs_distrito_8.append(doc)
        except:
            continue
    
    print(f"   Documentos con distrito = '8': {len(docs_distrito_8)}")
    
    for doc in docs_distrito_8[:10]:
        try:
            data = json.loads(doc.content)
            print(f"   - ID: {doc.id}, Source ID: {doc.source_id}")
            print(f"     Titulo: {data.get('title', 'Sin titulo')}")
            print(f"     Distrito: {data.get('district', 'Sin distrito')}")
            print(f"     Direccion: {data.get('real_address', 'Sin direccion')}")
            print(f"     Embedding: {'Si' if doc.has_embedding else 'No'}")
        except:
            print(f"   - ID: {doc.id} (error parseando)")
        print()
    
    print()
    
    # 4. Verificar embeddings
    print("4. ESTADO DE EMBEDDINGS")
    total_docs = collection.documents.count()
    docs_with_embedding = collection.documents.filter(has_embedding=True).count()
    docs_without_embedding = collection.documents.filter(has_embedding=False).count()
    
    print(f"   Total documentos: {total_docs}")
    print(f"   Con embedding: {docs_with_embedding} ({docs_with_embedding/total_docs*100:.1f}%)")
    print(f"   Sin embedding: {docs_without_embedding} ({docs_without_embedding/total_docs*100:.1f}%)")
    
    # Verificar si los documentos de Cerro Colorado tienen embedding
    print()
    print("   Embeddings para documentos de Cerro Colorado:")
    for doc in docs_distrito_8[:5]:
        print(f"   - ID {doc.id}: {'Tiene embedding' if doc.has_embedding else 'NO tiene embedding'}")
    
    print()
    
    # 5. Verificar busqueda vectorial
    print("5. SIMULANDO BUSQUEDA VECTORIAL")
    print("   (Esta es una simulacion - el sistema real usa embeddings de 384 dimensiones)")
    
    # Ejemplo de consulta que el usuario haria
    query = "propiedades en Cerro Colorado"
    print(f"   Consulta de ejemplo: '{query}'")
    
    # Verificar si hay documentos que coincidan con la consulta
    matching_docs = []
    for doc in all_docs[:50]:  # Revisar solo los primeros 50 por eficiencia
        try:
            data = json.loads(doc.content)
            content_lower = doc.content.lower()
            query_lower = query.lower()
            
            # Verificar coincidencias simples
            if 'cerro colorado' in content_lower:
                matching_docs.append({
                    'id': doc.id,
                    'source_id': doc.source_id,
                    'title': data.get('title', ''),
                    'district': data.get('district', ''),
                    'has_embedding': doc.has_embedding,
                    'match_type': 'texto directo'
                })
            elif data.get('district') == '8':
                matching_docs.append({
                    'id': doc.id,
                    'source_id': doc.source_id,
                    'title': data.get('title', ''),
                    'district': data.get('district', ''),
                    'has_embedding': doc.has_embedding,
                    'match_type': 'distrito 8'
                })
        except:
            continue
    
    print(f"   Documentos que coinciden con la consulta: {len(matching_docs)}")
    for match in matching_docs[:5]:
        print(f"   - ID {match['id']}: {match['title']}")
        print(f"     Distrito: {match['district']}, Embedding: {match['has_embedding']}, Tipo: {match['match_type']}")
    
    print()
    
    # 6. Analisis de la inconsistencia
    print("6. ANALISIS DE LA INCONSISTENCIA")
    print("   Escenario reportado por el usuario:")
    print("   1. Usuario pregunta: 'que propiedades tienes en cayma que me puedas mostrar'")
    print("   2. Sistema responde: 'No tengo informacion especifica sobre propiedades disponibles en Cayma'")
    print("   3. Usuario pregunta: 'que propiedades tiene'")
    print("   4. Sistema muestra lista que incluye propiedad en Cerro Colorado")
    print()
    print("   Posibles causas:")
    
    if len(docs_distrito_8) > 0:
        print("   [OK] HAY propiedades en Cerro Colorado en la base de datos")
        print("   [ERROR] Pero el sistema RAG no las encuentra cuando se busca especificamente")
        print()
        print("   Causas posibles:")
        print("   1. Embeddings no generados para esas propiedades")
        print("   2. Busqueda vectorial con umbral de similitud muy alto")
        print("   3. Consulta mal formulada para busqueda semantica")
        print("   4. El LLM (DeepSeek) esta generando respuestas sin usar RAG")
    else:
        print("   [ERROR] NO HAY propiedades en Cerro Colorado en la base de datos")
        print("   [OK] Entonces cuando el sistema dice 'no hay propiedades', es correcto")
        print("   [ERROR] Pero luego muestra una lista que INCLUYE Cerro Colorado (¿error del LLM?)")
    
    print()
    print("=== FIN DEL ANALISIS ===")

if __name__ == "__main__":
    investigar_inconsistencia()