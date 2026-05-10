"""Script para verificar los campos FK en los documentos de la colección propiedades_propify."""
import django
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from intelligence.models import IntelligenceDocument

docs = IntelligenceDocument.objects.filter(collection__name='propiedades_propify')[:3]
for d in docs:
    fv = d.field_values or {}
    # Mostrar campos FK y resueltos
    fk_keys = [k for k in fv.keys() if any(x in k.lower() for x in ['district','condition','currency','operation','property_type','status','owner','_fk','_id','_name'])]
    print(f'Doc {d.source_id}:')
    for k in sorted(fk_keys):
        print(f'  {k}: {fv.get(k)}')
    print('---')

# También mostrar cuántos campos total tiene cada documento
print(f"\nTotal documentos: {IntelligenceDocument.objects.filter(collection__name='propiedades_propify').count()}")
print(f"Campos promedio por documento: ~{sum(len(d.field_values or {}) for d in docs) // len(docs)}")
