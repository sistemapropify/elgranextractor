import sys, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from intelligence.models import IntelligenceDocument, IntelligenceCollection
from intelligence.services.rag import RAGService

c = IntelligenceCollection.objects.get(name='propiedades_propify')
docs = IntelligenceDocument.objects.filter(collection=c).order_by('?')[:3]

print("=== 3 DOCUMENTOS ALEATORIOS ===")
for d in docs:
    fv = d.field_values or {}
    district = fv.get('district_name', 'N/A')
    condition = fv.get('condition_name', 'N/A')
    op_type = fv.get('operation_type_name', 'N/A')
    prop_type = fv.get('property_type_name', 'N/A')
    title = fv.get('title', '')[:60]
    print(f"  ID={d.source_id} | Distrito: {district} | Condicion: {condition} | Tipo: {op_type}/{prop_type}")
    print(f"  Titulo: {title}")
    print()

print("=== BUSQUEDA: 'busca propiedades en cayma' ===")
results = RAGService.search_dynamic('busca propiedades en cayma', ['propiedades_propify'], top_k=5)
print(f"Resultados: {len(results)}")
for r in results:
    fv = r.get('field_values', {})
    score = r.get('score', 0)
    district = fv.get('district_name', 'N/A')
    title = fv.get('title', '')[:60]
    print(f"  Score: {score:.4f} | Distrito: {district} | {title}")

print()
print("=== BUSQUEDA: 'departamentos en venta en cerro colorado' ===")
results2 = RAGService.search_dynamic('departamentos en venta en cerro colorado', ['propiedades_propify'], top_k=5)
print(f"Resultados: {len(results2)}")
for r in results2:
    fv = r.get('field_values', {})
    score = r.get('score', 0)
    district = fv.get('district_name', 'N/A')
    title = fv.get('title', '')[:60]
    print(f"  Score: {score:.4f} | Distrito: {district} | {title}")
