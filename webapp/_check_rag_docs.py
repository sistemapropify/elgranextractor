import django, os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument

c = IntelligenceCollection.objects.get(name='propiedades_propify')
docs = IntelligenceDocument.objects.filter(collection=c)[:5]
for d in docs:
    print(f'ID={d.id}')
    print(f'  source_id={d.source_id}')
    print(f'  content[:500]: {d.content[:500] if d.content else "None"}')
    fv = d.field_values or {}
    print(f'  field_values keys: {list(fv.keys())}')
    print(f'  field_values.district: {fv.get("district", "NOT FOUND")}')
    print(f'  field_values.title: {fv.get("title", "NOT FOUND")}')
    print(f'  field_values.description: {str(fv.get("description", ""))[:200]}')
    print('---')
