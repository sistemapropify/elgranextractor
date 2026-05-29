"""
Script de depuración para sincronización de colecciones.
Ejecutar desde webapp/: py -3 ../_debug_sync.py
"""
import django
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))

django.setup()

from intelligence.models import IntelligenceCollection
from intelligence.services.rag import RAGService

# 1. Verificar colección
cid = 'c4856091-0ed2-493f-b391-c0b2f727ddc8'
try:
    collection = IntelligenceCollection.objects.get(id=cid)
    print('=== COLECCIÓN ENCONTRADA ===')
    print(f'Nombre: {collection.name}')
    print(f'Table: {collection.table_name}')
    print(f'Source SQL: {str(collection.source_sql)[:200] if collection.source_sql else "VACÍO"}')
    print(f'Database alias: {collection.database_alias}')
    print(f'Active: {collection.is_active}')
    print(f'Embedding fields: {collection.embedding_fields}')
    print(f'Field definitions keys count: {len(collection.field_definitions or {})}')
    print(f'Relationships: {collection.table_relationships}')
    print(f'Last sync: {collection.last_sync_at}')
    print(f'Last sync count: {collection.last_sync_count}')
    
    # 2. Intentar sync
    print('\n=== SINCRONIZANDO... ===')
    sys.stdout.flush()
    success, message, stats = RAGService.sync_collection_dynamic(
        collection_name=collection.name,
        force_full_sync=True,
    )
    print(f'Success: {success}')
    print(f'Message: {message}')
    print(f'Stats: {stats}')
    
    # 3. Contar documentos después del sync
    from intelligence.models import IntelligenceDocument
    doc_count = IntelligenceDocument.objects.filter(collection=collection).count()
    docs_with_emb = IntelligenceDocument.objects.filter(collection=collection, embedding__isnull=False).count()
    print(f'\nDocumentos después del sync: {doc_count} total, {docs_with_emb} con embedding')
    
except IntelligenceCollection.DoesNotExist:
    print(f'ERROR: Colección {cid} no encontrada')
except Exception as e:
    import traceback
    print(f'ERROR: {type(e).__name__}: {e}')
    traceback.print_exc()
