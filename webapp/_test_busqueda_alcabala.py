# -*- coding: utf-8 -*-
import os, sys, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, '.')
django.setup()

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from intelligence.services.rag import RAGService
from intelligence.models import IntelligenceCollection, IntelligenceDocument
from django.db.models import Q

print("=" * 80)
print("TEST 1: Busqueda directa en BD por contenido 'alcabala'")
print("=" * 80)

col = IntelligenceCollection.objects.get(name='propiedades_propify')
docs = IntelligenceDocument.objects.filter(
    collection=col,
    content__icontains='alcabala'
)
print(f"Documentos con 'alcabala' en content: {docs.count()}")
for d in docs:
    print(f"  ID={d.id}, source_id={d.source_id}")
    print(f"  content (primeros 500): {str(d.content)[:500]}")

print("\n" + "=" * 80)
print("TEST 2: Busqueda directa en BD por contenido 'coworking'")
print("=" * 80)

docs2 = IntelligenceDocument.objects.filter(
    collection=col,
    content__icontains='coworking'
)
print(f"Documentos con 'coworking' en content: {docs2.count()}")
for d in docs2:
    print(f"  ID={d.id}, source_id={d.source_id}")
    print(f"  content (primeros 500): {str(d.content)[:500]}")

print("\n" + "=" * 80)
print("TEST 3: Busqueda directa en BD por contenido 'terraza'")
print("=" * 80)

docs3 = IntelligenceDocument.objects.filter(
    collection=col,
    content__icontains='terraza'
)
print(f"Documentos con 'terraza' en content: {docs3.count()}")
for d in docs3:
    print(f"  ID={d.id}, source_id={d.source_id}")
    print(f"  title: {d.field_values.get('title', 'N/A')}")

print("\n" + "=" * 80)
print("TEST 4: Probar RAGService.search_dynamic con 'alcabala'")
print("=" * 80)

# Temporalmente bajar el threshold para ver resultados
old_threshold = RAGService.SIMILARITY_THRESHOLD
RAGService.SIMILARITY_THRESHOLD = 0.0

results = RAGService.search_dynamic(
    query="no pagar alcabala",
    collection_names=['propiedades_propify'],
    top_k=10
)

print(f"Resultados: {len(results)}")
for i, r in enumerate(results):
    print(f"\n--- Resultado {i+1} ---")
    print(f"  search_type: {r.get('search_type', 'N/A')}")
    print(f"  similarity: {r.get('similarity', 'N/A')}")
    # field_values es un dict anidado
    fv = r.get('field_values', {})
    print(f"  field_values keys: {list(fv.keys())}")
    print(f"  title (desde field_values): {fv.get('title', 'N/A')}")
    print(f"  description (desde field_values, primeros 300): {str(fv.get('description', ''))[:300]}")
    print(f"  content directo (primeros 300): {str(r.get('content', ''))[:300]}")

RAGService.SIMILARITY_THRESHOLD = old_threshold

print("\n" + "=" * 80)
print("TEST 5: Probar RAGService.search_dynamic con 'coworking'")
print("=" * 80)

RAGService.SIMILARITY_THRESHOLD = 0.0
results2 = RAGService.search_dynamic(
    query="coworking",
    collection_names=['propiedades_propify'],
    top_k=10
)
print(f"Resultados: {len(results2)}")
for i, r in enumerate(results2):
    print(f"\n--- Resultado {i+1} ---")
    print(f"  search_type: {r.get('search_type', 'N/A')}")
    print(f"  similarity: {r.get('similarity', 'N/A')}")
    fv = r.get('field_values', {})
    print(f"  title (desde field_values): {fv.get('title', 'N/A')}")
    print(f"  description (desde field_values, primeros 300): {str(fv.get('description', ''))[:300]}")
RAGService.SIMILARITY_THRESHOLD = old_threshold

print("\n" + "=" * 80)
print("TEST 6: Probar RAGService.search_dynamic con 'terraza'")
print("=" * 80)

RAGService.SIMILARITY_THRESHOLD = 0.0
results3 = RAGService.search_dynamic(
    query="terraza",
    collection_names=['propiedades_propify'],
    top_k=10
)
print(f"Resultados: {len(results3)}")
for i, r in enumerate(results3):
    print(f"\n--- Resultado {i+1} ---")
    print(f"  search_type: {r.get('search_type', 'N/A')}")
    print(f"  similarity: {r.get('similarity', 'N/A')}")
    fv = r.get('field_values', {})
    print(f"  title (desde field_values): {fv.get('title', 'N/A')}")
    print(f"  description (desde field_values, primeros 300): {str(fv.get('description', ''))[:300]}")
RAGService.SIMILARITY_THRESHOLD = old_threshold

print("\n" + "=" * 80)
print("TEST 7: Ver configuracion de la coleccion")
print("=" * 80)
print(f"Nombre: {col.name}")
print(f"embedding_fields: {col.embedding_fields}")
print(f"display_fields: {col.display_fields}")
print(f"field_definitions: {str(col.field_definitions)[:500]}")
print(f"table_name: {col.table_name}")
print(f"source_sql: {str(col.source_sql)[:300]}")

print("\n" + "=" * 80)
print("TEST 8: Ver field_values del documento con alcabala")
print("=" * 80)
for d in docs:
    print(f"Documento ID={d.id}, source_id={d.source_id}")
    print(f"field_values keys: {list(d.field_values.keys()) if d.field_values else 'VACIO'}")
    print(f"field_values (completo): {json.dumps(d.field_values, ensure_ascii=False, indent=2)[:1000]}")
    print(f"display_fields de coleccion: {col.display_fields}")

print("\nDIAGNOSTICO COMPLETADO")
