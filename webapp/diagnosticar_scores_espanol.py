"""
Script para diagnosticar los scores de similitud con el nuevo modelo español.
"""
import os
import sys
import django
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.services.rag import RAGService
from intelligence.models import IntelligenceCollection, IntelligenceDocument

def diagnosticar_scores():
    """Calcula scores de similitud para varias consultas y muestra la distribución."""
    RAGService.initialize_embedder()
    print(f"Modelo: {RAGService.EMBEDDING_MODEL}")
    print(f"Threshold actual: {RAGService.SIMILARITY_THRESHOLD}")
    
    try:
        collection = IntelligenceCollection.objects.get(name="propiedades_propify")
        docs = list(IntelligenceDocument.objects.filter(
            collection=collection,
            embedding__isnull=False
        ).select_related('collection'))
        print(f"Documentos con embedding: {len(docs)}")
    except IntelligenceCollection.DoesNotExist:
        print("Colección no encontrada")
        return
    
    consultas = [
        "Cerro Colorado",
        "Cayma",
        "Yanahuara",
        "Sachaca",
        "Cercado",
        "departamento en Cerro Colorado",
        "casa en Cayma",
        "terreno en venta",
    ]
    
    for consulta in consultas:
        print(f"\n{'='*60}")
        print(f"CONSULTA: '{consulta}'")
        print(f"{'='*60}")
        
        query_embedding = RAGService.generate_embedding(consulta)
        if not query_embedding:
            print("  ERROR: No se pudo generar embedding")
            continue
        
        query_vector = np.frombuffer(query_embedding, dtype=np.float32)
        
        scores = []
        for doc in docs:
            try:
                doc_vector = np.frombuffer(doc.embedding, dtype=np.float32)
                similarity = float(np.dot(query_vector, doc_vector) / (
                    np.linalg.norm(query_vector) * np.linalg.norm(doc_vector)
                ))
                
                # Extraer distrito del field_values
                district = doc.field_values.get('district', 'N/A')
                title = doc.field_values.get('title', 'N/A')[:60]
                
                scores.append((similarity, district, title))
            except Exception as e:
                pass
        
        # Ordenar por score descendente
        scores.sort(key=lambda x: x[0], reverse=True)
        
        print(f"  Top 10 scores:")
        for i, (score, district, title) in enumerate(scores[:10], 1):
            print(f"  [{i}] Score: {score:.4f} | Distrito: {district} | {title}")
        
        # Estadísticas
        above_05 = sum(1 for s, _, _ in scores if s >= 0.5)
        above_04 = sum(1 for s, _, _ in scores if s >= 0.4)
        above_03 = sum(1 for s, _, _ in scores if s >= 0.3)
        above_02 = sum(1 for s, _, _ in scores if s >= 0.2)
        max_score = scores[0][0] if scores else 0
        min_score = scores[-1][0] if scores else 0
        
        print(f"\n  Estadísticas:")
        print(f"  Max score: {max_score:.4f}")
        print(f"  Min score: {min_score:.4f}")
        print(f"  Docs >= 0.5: {above_05}")
        print(f"  Docs >= 0.4: {above_04}")
        print(f"  Docs >= 0.3: {above_03}")
        print(f"  Docs >= 0.2: {above_02}")

if __name__ == '__main__':
    diagnosticar_scores()
