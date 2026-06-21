import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
sys.path.insert(0, os.path.dirname(__file__))
import django; django.setup()

from intelligence.services.rag import RAGService
from intelligence.models import IntelligenceDocument, IntelligenceCollection
import sys

c = IntelligenceCollection.objects.get(name='propiedadespropify')

print(f"=== RE-SINCRONIZANDO {c.name} === ")
print(f"Source SQL: {c.source_sql}")
print(f"Documentos actuales en RAG: {IntelligenceDocument.objects.filter(collection=c).count()}")

# Borrar documentos existentes para forzar recreación limpia
print("\nEliminando documentos existentes...")
deleted, _ = IntelligenceDocument.objects.filter(collection=c).delete()
print(f"Eliminados: {deleted}")

# Sincronizar desde cero
print("\nSincronizando con sync_collection_dynamic...")
sys.stdout.flush()
success, message, stats = RAGService.sync_collection_dynamic(
    collection_name=c.name,
    force_full_sync=True,
)
print(f"\nSuccess: {success}")
print(f"Message: {message}")
print(f"Stats: {stats}")

# Verificar resultado
docs_ok = IntelligenceDocument.objects.filter(collection=c).count()
emb_ok = IntelligenceDocument.objects.filter(collection=c, embedding__isnull=False).count()
print(f"\nDocumentos post-sync: {docs_ok} total, {emb_ok} con embedding")
