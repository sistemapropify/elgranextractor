import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
import django
django.setup()

from intelligence.models import IntelligenceCollection
from intelligence.services.faiss_index import FAISSIndexManager

# Check collection
col = IntelligenceCollection.objects.get(name='propiedadespropify')
print(f"Collection: {col.name}")
print(f"  embedding_model: {col.embedding_model}")
print(f"  vector_dimension: {col.vector_dimension}")
print(f"  is_active: {col.is_active}")
print(f"  documents: {col.documents.count()}")

# Rebuild
print("\nRebuilding FAISS index...")
n = FAISSIndexManager.rebuild_for_collection('propiedadespropify')
print(f"Vectors indexed: {n}")
