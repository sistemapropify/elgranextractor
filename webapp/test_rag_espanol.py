"""
Script de prueba para verificar que el modelo de embeddings en español
encuentra propiedades correctamente por distrito y otros criterios.
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.services.rag import RAGService
from intelligence.models import IntelligenceCollection
import json

def test_busqueda(consulta, top_k=5):
    """Prueba una búsqueda semántica y muestra resultados."""
    print(f"\n{'='*70}")
    print(f"CONSULTA: '{consulta}'")
    print(f"{'='*70}")
    
    try:
        results = RAGService.search_dynamic(
            query=consulta,
            collection_names=["propiedades_propify"],
            top_k=top_k
        )
        
        if not results:
            print("  → Sin resultados")
            return []
        
        print(f"  Resultados encontrados: {len(results)}")
        for i, r in enumerate(results, 1):
            score = r.get('similarity', r.get('score', 0))
            content = r.get('content', '')
            field_values = r.get('field_values', {})
            
            # Extraer info relevante
            title = field_values.get('title', '') or (json.loads(content).get('title', '') if isinstance(content, str) and content.startswith('{') else '')
            district = field_values.get('district', '') or (json.loads(content).get('district', '') if isinstance(content, str) and content.startswith('{') else '')
            price = field_values.get('price', '') or (json.loads(content).get('price', '') if isinstance(content, str) and content.startswith('{') else '')
            
            print(f"\n  [{i}] Score: {score:.4f}")
            print(f"      Título: {title}")
            print(f"      Distrito: {district}")
            print(f"      Precio: {price}")
        
        return results
        
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    # Inicializar el modelo
    print("Inicializando modelo de embeddings...")
    RAGService.initialize_embedder()
    print(f"Modelo: {RAGService.EMBEDDING_MODEL}")
    
    # Verificar documentos en la colección
    try:
        collection = IntelligenceCollection.objects.get(name="propiedades_propify")
        doc_count = collection.documents.count()
        with_embedding = collection.documents.exclude(embedding__isnull=True).count()
        print(f"Colección: {collection.name} ({doc_count} docs, {with_embedding} con embedding)")
    except IntelligenceCollection.DoesNotExist:
        print("Colección 'propiedades_propify' no encontrada")
        return
    
    # Pruebas de búsqueda
    consultas = [
        "Cerro Colorado",
        "Cayma",
        "Yanahuara",
        "Sachaca",
        "Cercado",
        "departamento en Cerro Colorado",
        "casa en Cayma",
        "terreno en venta",
        "departamento con cochera",
        "casa con 3 dormitorios",
        "Miraflores",
        "José Luis Bustamante y Rivero",
    ]
    
    for consulta in consultas:
        test_busqueda(consulta, top_k=3)
    
    print(f"\n{'='*70}")
    print("PRUEBAS COMPLETADAS")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
