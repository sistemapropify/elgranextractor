"""
Verificar el documento DUPLEX y sus field_values.
"""
import sys, os, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.models import IntelligenceDocument, IntelligenceCollection

c = IntelligenceCollection.objects.get(name='propiedades_propify')
docs = IntelligenceDocument.objects.filter(collection=c)

output = []
for doc in docs:
    fv = doc.field_values or {}
    title = fv.get('title', '')
    if 'DUPLEX' in str(title):
        output.append(f"source_id={doc.source_id}, title={title}")
        output.append(f"  district={fv.get('district')}")
        output.append(f"  district_name={fv.get('district_name', 'NOT FOUND')}")
        output.append(f"  district_fk_id={fv.get('district_fk_id', 'NOT FOUND')}")
        # Mostrar todas las keys
        for k in sorted(fv.keys()):
            output.append(f"  {k}: {fv[k]}")
        break

out_path = os.path.join(os.path.dirname(__file__), '_duplex_output.txt')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))
print(f"Output saved to {out_path}")
