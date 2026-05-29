"""
Script de depuración para sincronización de colecciones.
Ejecutar: cd webapp && py -3 _debug_sync.py
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from intelligence.models import IntelligenceCollection
from intelligence.services.rag import RAGService

cid = 'c4856091-0ed2-493f-b391-c0b2f727ddc8'
try:
    collection = IntelligenceCollection.objects.get(id=cid)
    print('=== COLECCION ENCONTRADA ===')
    print(f'Nombre: {collection.name}')
    print(f'Table: {collection.table_name}')
    print(f'Source SQL: {str(collection.source_sql)[:200] if collection.source_sql else "VACIO"}')
    print(f'Database alias: {collection.database_alias}')
    print(f'Active: {collection.is_active}')
    print(f'Embedding fields: {collection.embedding_fields}')
    print(f'Field definitions keys count: {len(collection.field_definitions or {})}')
    print(f'Display fields: {collection.display_fields}')
    print(f'Relationships: {collection.table_relationships}')
    print(f'Semantic tags: {collection.semantic_tags}')
    print(f'Last sync: {collection.last_sync_at}')
    print(f'Last sync count: {collection.last_sync_count}')
    
    if collection.table_name:
        print(f'\nTiene table_name: "{collection.table_name}" -> ES DINAMICA')
        print('\n=== SINCRONIZANDO... ===')
        sys.stdout.flush()
        success, message, stats = RAGService.sync_collection_dynamic(
            collection_name=collection.name,
            force_full_sync=True,
        )
        print(f'Success: {success}')
        print(f'Message: {message}')
        print(f'Stats: {stats}')
        
        # Contar docs post-sync
        from intelligence.models import IntelligenceDocument
        doc_count = IntelligenceDocument.objects.filter(collection=collection).count()
        docs_with_emb = IntelligenceDocument.objects.filter(collection=collection, embedding__isnull=False).count()
        print(f'\nDocumentos post-sync: {doc_count} total, {docs_with_emb} con embedding')
    else:
        print('\nNO tiene table_name -> ES LEGACY')
        
except IntelligenceCollection.DoesNotExist:
    print(f'ERROR: Coleccion {cid} no encontrada')
except Exception as e:
    import traceback
    print(f'ERROR: {type(e).__name__}: {e}')
    traceback.print_exc()
