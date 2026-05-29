import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from intelligence.services.rag import RAGService
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

print("Iniciando sincronizacion de coleccion 'propiedadespropify'...")
success, message, stats = RAGService.sync_collection_dynamic(
    collection_name='propiedadespropify',
    force_full_sync=True,
)
print(f"Success: {success}")
print(f"Message: {message}")
print(f"Stats: {stats}")
