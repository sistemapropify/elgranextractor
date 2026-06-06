import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.chdir('webapp')
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument
from django.db.models import Count

# Check collection exists
try:
    col = IntelligenceCollection.objects.get(name='propiedades_propify')
    doc_count = IntelligenceDocument.objects.filter(collection=col).count()
    print(f"Collection 'propiedades_propify': {doc_count} documents")
    
    # Delete documents first, then collection
    deleted_docs = IntelligenceDocument.objects.filter(collection=col).delete()
    print(f"Deleted documents: {deleted_docs}")
    
    deleted_col = col.delete()
    print(f"Deleted collection: {deleted_col}")
except IntelligenceCollection.DoesNotExist:
    print("Collection 'propiedades_propify' not found in DB (already deleted)")

# Verify remaining
remaining = IntelligenceCollection.objects.all()
print(f"\nRemaining collections:")
for c in remaining:
    docs = IntelligenceDocument.objects.filter(collection=c).count()
    print(f"  {c.name}: {docs} documents")
