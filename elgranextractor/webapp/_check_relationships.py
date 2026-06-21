"""
Verificar relaciones entre tablas y contenido de documentos.
"""
import sys, os, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument

collection = IntelligenceCollection.objects.get(name='propiedades_propify')

print('=== RELACIONES CONFIGURADAS ===')
rels = collection.table_relationships
print(f'  Cantidad: {len(rels)}')
for r in rels:
    print(f'  - {r}')

print('\n=== PRIMEROS 3 DOCUMENTOS ===')
docs = IntelligenceDocument.objects.filter(collection=collection)[:3]
for doc in docs:
    print(f'\n  Documento source_id={doc.source_id}:')
    fv = doc.field_values or {}
    # Mostrar campos clave
    for key in ['title', 'price', 'currency_id', 'district', 'district_fk_id', 
                'urbanization', 'urbanization_fk_id', 'operation_type_id',
                'property_type_id', 'condition_id']:
        if key in fv:
            print(f'    {key}: {fv[key]}')
    # Mostrar contenido del embedding (primeros 300 chars)
    content = doc.content or ''
    print(f'    content[:300]: {content[:300]}')
    print(f'    ---')

print('\n=== VERIFICAR SI HAY FK RESUELTOS EN CONTENT ===')
docs_all = IntelligenceDocument.objects.filter(collection=collection)
total = docs_all.count()
with_fk_resolved = 0
for doc in docs_all:
    content = doc.content or ''
    if 'District Fk:' in content or 'Cayma' in content or 'Yanahuara' in content:
        with_fk_resolved += 1

print(f'  Total documentos: {total}')
print(f'  Con FK resueltos en content: {with_fk_resolved}')

# Mostrar un content completo de ejemplo
if total > 0:
    doc = docs_all[0]
    print(f'\n=== CONTENT COMPLETO DEL DOCUMENTO {doc.source_id} ===')
    print(doc.content)
