"""Script para verificar qué campos resueltos existen en los documentos."""
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from intelligence.models import IntelligenceDocument

doc = IntelligenceDocument.objects.filter(collection__name='propiedades_propify').first()
fv = doc.field_values or {}

# Buscar campos que empiecen con province, unit_location, o que terminen en _name
print("=== Campos que terminan en _name ===")
for k in sorted(fv.keys()):
    if k.endswith('_name'):
        print(f'  {k}: {fv.get(k)}')

print("\n=== Campos que contienen 'province' o 'unit' ===")
for k in sorted(fv.keys()):
    if 'province' in k.lower() or 'unit' in k.lower():
        print(f'  {k}: {fv.get(k)}')

print("\n=== embedding_fields actuales ===")
from intelligence.models import IntelligenceCollection
c = IntelligenceCollection.objects.get(name='propiedades_propify')
print(f'embedding_fields: {c.embedding_fields}')
print(f'display_fields: {c.display_fields}')
