"""
Verificar relaciones FK configuradas en la coleccion.
"""
import sys, os, json, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.models import IntelligenceCollection

c = IntelligenceCollection.objects.get(name='propiedades_propify')

output = []

output.append("=== FK RELATIONSHIPS ===")
rels = c.relationships
if isinstance(rels, list):
    for r in rels:
        output.append(json.dumps(r, indent=2, ensure_ascii=False))
elif isinstance(rels, str):
    output.append(json.loads(rels))
elif rels is None:
    output.append("No relationships configured")
else:
    output.append(f"Type: {type(rels)}")
    output.append(str(rels)[:1000])

output.append("")
output.append("=== FIELD DEFINITIONS (FK-related) ===")
fd = c.field_definitions or {}
for k, v in fd.items():
    if 'fk' in k.lower() or 'district' in k.lower() or 'urbanization' in k.lower():
        output.append(f"  {k}: {v}")

out_path = os.path.join(os.path.dirname(__file__), '_relationships_output.txt')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))
print(f"Output saved to {out_path}")
