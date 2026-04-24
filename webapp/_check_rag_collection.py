import django, os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument

c = IntelligenceCollection.objects.get(name='propiedades_propify')
print('=== COLECCIÓN: propiedades_propify ===')
print(f'source_sql: {c.source_sql[:800] if c.source_sql else "None"}')
print(f'embedding_fields: {c.embedding_fields}')
print(f'display_fields: {c.display_fields}')
print(f'field_definitions keys: {list(c.field_definitions.keys()) if c.field_definitions else "None"}')

print(f'\n=== DOCUMENTOS (primeros 5) ===')
docs = IntelligenceDocument.objects.filter(collection=c)[:5]
for d in docs:
    content_preview = d.content[:300] if d.content else 'None'
    print(f'ID={d.id}, title={d.title}')
    print(f'  content: {content_preview}')
    print(f'  metadata: {json.dumps(d.metadata, indent=2)[:300]}')
    print('---')
