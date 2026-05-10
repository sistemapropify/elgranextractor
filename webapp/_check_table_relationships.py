"""
Verificar table_relationships configuradas en la coleccion.
"""
import sys, os, json, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.models import IntelligenceCollection

c = IntelligenceCollection.objects.get(name='propiedades_propify')

output = []
output.append("=== TABLE RELATIONSHIPS ===")
rels = c.table_relationships
if isinstance(rels, list):
    output.append(f"Total relationships: {len(rels)}")
    for i, r in enumerate(rels):
        output.append(f"\n--- Relationship {i+1} ---")
        output.append(json.dumps(r, indent=2, ensure_ascii=False))
elif rels is None:
    output.append("No relationships configured (None)")
else:
    output.append(f"Type: {type(rels)}")
    output.append(str(rels)[:2000])

output.append("\n\n=== Verificando documento con district_fk_id=None ===")
from intelligence.models import IntelligenceDocument
# Buscar documento con district_fk_id=None
docs_con_district_none = IntelligenceDocument.objects.filter(
    collection=c,
    field_values__district_fk_id__isnull=True
)[:3]
output.append(f"Documentos con district_fk_id=None: {len(docs_con_district_none)}")
for doc in docs_con_district_none:
    fv = doc.field_values or {}
    output.append(f"\n  source_id={doc.source_id}")
    output.append(f"    district={fv.get('district')}")
    output.append(f"    district_fk_id={fv.get('district_fk_id')}")
    output.append(f"    district_name={fv.get('district_name', 'NOT FOUND')}")

# Documentos con district_fk_id con valor
docs_con_district_val = IntelligenceDocument.objects.filter(
    collection=c,
    field_values__district_fk_id__isnull=False
)[:3]
output.append(f"\n\nDocumentos con district_fk_id con valor: {len(docs_con_district_val)}")
for doc in docs_con_district_val:
    fv = doc.field_values or {}
    output.append(f"\n  source_id={doc.source_id}")
    output.append(f"    district={fv.get('district')}")
    output.append(f"    district_fk_id={fv.get('district_fk_id')}")
    output.append(f"    district_name={fv.get('district_name', 'NOT FOUND')}")

out_path = os.path.join(os.path.dirname(__file__), '_table_relationships_output.txt')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))
print(f"Output saved to {out_path}")
