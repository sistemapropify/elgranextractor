import django, os, sys, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.services.rag import RAGService
from intelligence.services.prompts import format_rag_context

print("=" * 60)
print("TEST 1: Búsqueda sin filtro (como antes)")
print("=" * 60)
results = RAGService.search_dynamic(
    query="propiedades en cayma",
    collection_names=["propiedades_propify"],
    top_k=10,
)
print(f"Resultados: {len(results)}")
for r in results:
    fv = r.get('field_values', {})
    print(f"  - {fv.get('title', '?')[:50]} | {fv.get('district_name', '?')} | sim={r.get('similarity', 0):.3f} | type={r.get('search_type', '?')}")

print()
print("=" * 60)
print("TEST 2: Búsqueda CON filtro de distrito (nuevo)")
print("=" * 60)
results2 = RAGService.search_dynamic(
    query="propiedades en cayma",
    collection_names=["propiedades_propify"],
    filters={"district_name": "Cayma"},
    top_k=10,
)
print(f"Resultados: {len(results2)}")
for r in results2:
    fv = r.get('field_values', {})
    print(f"  - {fv.get('title', '?')[:50]} | {fv.get('district_name', '?')} | sim={r.get('similarity', 0):.3f} | type={r.get('search_type', '?')}")

print()
print("=" * 60)
print("TEST 3: Formateo RAG context")
print("=" * 60)
rag_str = format_rag_context(results2, detailed=True)
print(rag_str[:1500])

sys.stdout.flush()
