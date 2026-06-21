import os
import sys
import django

sys.path.insert(0, 'webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument

# Obtener la colección
c = IntelligenceCollection.objects.get(name='propiedades_propify')
print(f"Colección: {c.name}")
print(f"Documentos totales: {c.documents.count()}")

# Contar documentos con y sin embedding
with_embedding = c.documents.filter(embedding__isnull=False).count()
without_embedding = c.documents.filter(embedding__isnull=True).count()

print(f"Documentos CON embedding: {with_embedding}")
print(f"Documentos SIN embedding: {without_embedding}")

# Verificar algunos documentos
print("\n--- Muestra de documentos ---")
docs = c.documents.all()[:5]
for i, doc in enumerate(docs, 1):
    has_embedding = bool(doc.embedding)
    print(f"Documento {i}: ID={doc.source_id}, Embedding={'SÍ' if has_embedding else 'NO'}")
    if doc.field_values:
        print(f"  Campos: {list(doc.field_values.keys())[:3]}...")
    print(f"  Contenido (primeros 50 chars): {doc.content[:50] if doc.content else 'Vacío'}...")

# Verificar si hay contenido en los documentos
print("\n--- Estadísticas de contenido ---")
empty_content = c.documents.filter(content__isnull=True).count() | c.documents.filter(content='').count()
print(f"Documentos sin contenido: {empty_content}")

# Probar una búsqueda más simple
print("\n--- Probando búsqueda alternativa ---")
from intelligence.services.rag import RAGService

# Buscar algo más genérico
simple_query = "propiedad"
try:
    results = RAGService.search_dynamic(
        query=simple_query,
        collection_names=['propiedades_propify'],
        filters={},
        top_k=3
    )
    print(f"Resultados para '{simple_query}': {len(results)}")
    for i, result in enumerate(results, 1):
        print(f"  {i}. Score: {result.get('score', 0):.4f}, ID: {result.get('source_id')}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()