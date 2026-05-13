"""
Verifica el estado de la colección después del resync con semantic_tags.
"""
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument

col = IntelligenceCollection.objects.get(name='propiedades_propify')
docs = IntelligenceDocument.objects.filter(collection=col)

print(f'Colección: {col.name}')
print(f'Tags: {col.semantic_tags}')
print(f'Total documentos: {docs.count()}')
print(f'Última sync: {col.last_sync_at}')
print(f'Registros en última sync: {col.last_sync_count}')

# Verificar que un documento tenga las tags inyectadas
if docs.exists():
    doc = docs.first()
    print(f'\nEjemplo documento {doc.source_id}:')
    print(f'  content[:400]: {doc.content[:400]}')
    print(f'  tiene tags: {"categoria:" in doc.content}')
else:
    print('\nNo hay documentos en la colección')
