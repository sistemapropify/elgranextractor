"""Script para verificar TODOS los campos de un documento de la colección propiedades_propify."""
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from intelligence.models import IntelligenceDocument

doc = IntelligenceDocument.objects.filter(collection__name='propiedades_propify').first()
fv = doc.field_values or {}
print(f'Todos los campos del documento (source_id={doc.source_id}):')
for k in sorted(fv.keys()):
    val = str(fv.get(k, ''))
    print(f'  {k}: {val}')
