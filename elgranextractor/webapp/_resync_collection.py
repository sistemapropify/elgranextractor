"""Script para re-sincronizar la colección propiedades_propify con los nuevos embedding_fields."""
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

import logging
logging.basicConfig(level=logging.INFO)

from intelligence.services.rag import RAGService

print("Iniciando re-sincronización de colección 'propiedades_propify'...")
print("(Esto regenerará embeddings usando los nuevos embedding_fields con nombres resueltos)")

success, message, stats = RAGService.sync_collection_dynamic(
    collection_name='propiedades_propify',
    force_full_sync=True  # Forzar regeneración de todos los embeddings
)

print(f"\nResultado: {'✅ ÉXITO' if success else '❌ ERROR'}")
print(f"Mensaje: {message}")
print(f"Stats: {stats}")
