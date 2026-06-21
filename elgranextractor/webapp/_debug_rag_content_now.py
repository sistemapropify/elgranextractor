import django, os, json, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()
from intelligence.models import IntelligenceCollection, IntelligenceDocument

c = IntelligenceCollection.objects.get(name='propiedades_propify')
print('EMBEDDING FIELDS:', c.embedding_fields, file=sys.stderr)
print('DISPLAY FIELDS:', c.display_fields, file=sys.stderr)

docs = IntelligenceDocument.objects.filter(collection=c)[:3]
for d in docs:
    print(f'--- source_id={d.source_id} ---', file=sys.stderr)
    fv = d.field_values or {}
    for k in sorted(fv.keys()):
        v = str(fv[k])[:150]
        print(f'  {k}: {v}', file=sys.stderr)
    print(f'  content[:500]: {(d.content or "")[:500]}', file=sys.stderr)
    print(file=sys.stderr)
