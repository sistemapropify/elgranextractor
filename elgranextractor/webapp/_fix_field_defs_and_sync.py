"""
Script para:
1. Convertir field_definitions de lista a diccionario
2. Sincronizar la colección propiedades_propify con datos reales
"""
import sys, os, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument
from django.db import connections

# 1. Convertir field_definitions de lista a dict
print('=== 1. CONVIRTIENDO FIELD_DEFINITIONS ===')
collection = IntelligenceCollection.objects.get(name='propiedades_propify')

if isinstance(collection.field_definitions, list):
    print(f'  field_definitions es lista con {len(collection.field_definitions)} elementos')
    new_defs = {}
    for field in collection.field_definitions:
        name = field.get('name', '')
        if name:
            new_defs[name] = {
                'type': field.get('type', 'string'),
                'is_nullable': field.get('is_nullable', True),
                'max_length': field.get('max_length', None),
            }
    collection.field_definitions = new_defs
    collection.save(update_fields=['field_definitions'])
    print(f'  Convertido a dict con {len(new_defs)} campos')
else:
    print(f'  field_definitions ya es dict con {len(collection.field_definitions)} campos')

# 2. Sincronizar
print('\n=== 2. SINCRONIZANDO ===')
from intelligence.services.rag import RAGService

success, message, stats = RAGService.sync_collection_dynamic(
    collection_name='propiedades_propify',
    force_full_sync=True,
    database_alias='propifai'
)

print(f'  Success: {success}')
print(f'  Message: {message}')
print(f'  Stats: {stats}')

# 3. Verificar documentos
print('\n=== 3. DOCUMENTOS CREADOS ===')
doc_count = IntelligenceDocument.objects.filter(collection=collection).count()
print(f'  Total documentos: {doc_count}')

if doc_count > 0:
    docs = IntelligenceDocument.objects.filter(collection=collection)[:3]
    for doc in docs:
        fv = doc.field_values or {}
        print(f'  source_id={doc.source_id}, title={fv.get("title", "N/A")}, price={fv.get("price", "N/A")}, district={fv.get("district", "N/A")}')

print('\n=== HECHO ===')
