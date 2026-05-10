"""Script para verificar exactamente qué campos duplicados existen."""
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from intelligence.models import IntelligenceDocument

doc = IntelligenceDocument.objects.filter(collection__name='propiedades_propify').first()
fv = doc.field_values or {}

# Mostrar TODOS los campos que terminan en _name, _code, _symbol, _description, _username, etc.
print("=== Todos los campos _name, _code, _symbol, _description, _username, _first_name, _last_name ===")
for k in sorted(fv.keys()):
    if any(k.endswith(s) for s in ['_name', '_code', '_symbol', '_description', '_username', '_first_name', '_last_name', '_maternal_last_name']):
        print(f'  {k}: {fv.get(k)}')

# También contar cuántos campos tiene cada documento
print(f'\nTotal campos en este documento: {len(fv)}')
