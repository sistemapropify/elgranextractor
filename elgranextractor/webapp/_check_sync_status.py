import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument

col = IntelligenceCollection.objects.get(name='propiedadespropify')
print(f'Coleccion: {col.name}')
print(f'Table: {col.table_name}')
print(f'DB alias: {col.database_alias}')
print(f'Sync count: {col.last_sync_count}')
print(f'Sync at: {col.last_sync_at}')

docs = IntelligenceDocument.objects.filter(collection=col)
print(f'Documentos totales: {docs.count()}')

if docs.exists():
    d = docs.first()
    print(f'Primer doc: source_id={d.source_id}')
    print(f'  content[:200]: {str(d.content)[:200] if d.content else "None"}')
    print(f'  has embedding: {d.embedding is not None}')
    print(f'  field_values keys: {list(d.field_values.keys())[:10] if d.field_values else "None"}')
else:
    print('No hay documentos. La sincronizacion no se ejecuto o fallo.')
