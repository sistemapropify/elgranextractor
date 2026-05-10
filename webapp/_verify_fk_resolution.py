"""
Verificar que los field_values ahora contienen nombres FK resueltos.
"""
import sys, os, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument

collection = IntelligenceCollection.objects.get(name='propiedades_propify')

print("=== VERIFICACION DE FK RESUELTOS EN FIELD_VALUES ===")
print()

# Contar documentos con campos FK resueltos
docs = IntelligenceDocument.objects.filter(collection=collection)
total = docs.count()
with_resolved = 0

for doc in docs:
    fv = doc.field_values or {}
    # Buscar campos terminados en _name
    resolved_keys = [k for k in fv.keys() if k.endswith('_name')]
    if resolved_keys:
        with_resolved += 1

print(f"Total documentos: {total}")
print(f"Documentos con campos _name resueltos: {with_resolved}")
print()

# Mostrar primeros 3 documentos con detalles
print("=== PRIMEROS 3 DOCUMENTOS CON DETALLE ===")
docs_sample = docs[:3]
for doc in docs_sample:
    fv = doc.field_values or {}
    print(f"\nDocumento source_id={doc.source_id}:")
    # Campos FK resueltos
    for key in sorted(fv.keys()):
        if key.endswith('_name'):
            print(f"  [FK RESUELTO] {key}: {fv[key]}")
    # Campos importantes
    for key in ['title', 'price', 'currency_id', 'district', 'district_fk_id']:
        if key in fv:
            print(f"  {key}: {fv[key]}")

print()
print("=== VERIFICACION DE FORMATO RAG ===")
# Simular lo que veria el LLM
from intelligence.services.prompts import format_rag_context
from intelligence.services.rag import RAGService

# Buscar documentos de ejemplo
resultados = RAGService.search_dynamic(
    query="propiedades en venta",
    collection_names=['propiedades_propify'],
    top_k=2
)

if resultados:
    rag_text = format_rag_context(resultados, detailed=True)
    print(rag_text[:2000])
else:
    print("No se encontraron resultados de busqueda")
