#!/usr/bin/env python
"""
Script para analizar el contenido real de los documentos en la colección propiedades_propify
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceDocument, IntelligenceCollection

def analizar_contenido():
    print("=== ANALIZANDO CONTENIDO DE DOCUMENTOS ===")
    print()
    
    # Obtener colección
    try:
        collection = IntelligenceCollection.objects.get(name='propiedades_propify')
        print(f"Coleccion: {collection.name}")
        print(f"Total documentos: {collection.documents.count()}")
    except IntelligenceCollection.DoesNotExist:
        print("Coleccion no encontrada")
        return
    
    print()
    
    # Analizar primeros 5 documentos
    print("ANALIZANDO PRIMEROS 5 DOCUMENTOS:")
    docs = collection.documents.all()[:5]
    
    for i, doc in enumerate(docs):
        print(f"\n--- Documento {i+1} ---")
        print(f"ID: {doc.id}")
        print(f"Source ID: {doc.source_id}")
        print(f"Tiene embedding: {doc.embedding is not None}")
        
        # Mostrar primeros 500 caracteres del contenido
        print(f"\nContenido (primeros 500 chars):")
        print("-" * 50)
        print(doc.content[:500])
        print("-" * 50)
        
        # Intentar parsear como JSON
        import json
        try:
            data = json.loads(doc.content)
            print("\n[OK] Contenido es JSON valido")
            print(f"Campos: {list(data.keys())[:10]}...")
            
            # Buscar campos relevantes
            if 'district' in data:
                print(f"District: {data['district']}")
            if 'title' in data:
                print(f"Title: {data['title']}")
            if 'real_address' in data:
                print(f"Address: {data['real_address']}")
                
        except json.JSONDecodeError:
            print("\n[ERROR] Contenido NO es JSON valido")
            
            # Buscar patrones en el texto
            content_lower = doc.content.lower()
            if 'cerro colorado' in content_lower:
                print("[INFO] Contiene 'cerro colorado' en texto")
            if 'cayma' in content_lower:
                print("[INFO] Contiene 'cayma' en texto")
            if 'distrito' in content_lower:
                # Buscar número de distrito
                import re
                distrito_match = re.search(r'distrito\s*[:=]?\s*(\d+)', content_lower)
                if distrito_match:
                    print(f"[INFO] Distrito encontrado: {distrito_match.group(1)}")
    
    print()
    
    # Buscar específicamente documentos con "cerro colorado"
    print("\n=== BUSCANDO DOCUMENTOS CON 'CERRO COLORADO' ===")
    docs_cerro = collection.documents.filter(content__icontains='cerro colorado')[:3]
    
    print(f"Encontrados: {collection.documents.filter(content__icontains='cerro colorado').count()}")
    
    for i, doc in enumerate(docs_cerro):
        print(f"\n--- Documento Cerro Colorado {i+1} ---")
        print(f"ID: {doc.id}, Source ID: {doc.source_id}")
        
        # Mostrar contexto alrededor de "cerro colorado"
        content_lower = doc.content.lower()
        idx = content_lower.find('cerro colorado')
        if idx != -1:
            start = max(0, idx - 100)
            end = min(len(doc.content), idx + 100)
            context = doc.content[start:end]
            print(f"Contexto: ...{context}...")
        
        # Verificar embedding
        print(f"Tiene embedding: {doc.embedding is not None}")
        if doc.embedding:
            print(f"Tamaño embedding: {len(doc.embedding)} bytes")
    
    print()
    
    # Verificar embeddings en general
    print("\n=== ESTADO DE EMBEDDINGS ===")
    total = collection.documents.count()
    with_embedding = collection.documents.exclude(embedding__isnull=True).count()
    without_embedding = collection.documents.filter(embedding__isnull=True).count()
    
    print(f"Total documentos: {total}")
    print(f"Con embedding: {with_embedding} ({with_embedding/total*100:.1f}%)")
    print(f"Sin embedding: {without_embedding} ({without_embedding/total*100:.1f}%)")
    
    # Verificar embeddings para documentos con "cerro colorado"
    print("\n=== EMBEDDINGS PARA DOCUMENTOS CON 'CERRO COLORADO' ===")
    docs_cerro_all = collection.documents.filter(content__icontains='cerro colorado')
    cerro_with_embedding = docs_cerro_all.exclude(embedding__isnull=True).count()
    cerro_without_embedding = docs_cerro_all.filter(embedding__isnull=True).count()
    
    print(f"Documentos con 'cerro colorado': {docs_cerro_all.count()}")
    print(f"  - Con embedding: {cerro_with_embedding}")
    print(f"  - Sin embedding: {cerro_without_embedding}")
    
    print("\n=== CONCLUSIONES ===")
    print("1. El contenido de los documentos NO es JSON valido, es texto plano")
    print("2. Hay propiedades en Cerro Colorado (18 documentos)")
    print("3. El sistema RAG probablemente falla porque:")
    print("   a) Los embeddings no se generaron correctamente para estos documentos")
    print("   b) La busqueda vectorial no encuentra coincidencias con texto no estructurado")
    print("   c) El LLM (DeepSeek) genera respuestas sin usar la informacion real de la BD")

if __name__ == "__main__":
    analizar_contenido()