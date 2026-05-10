"""
Verificar display_fields y field_definitions de la coleccion.
"""
import sys, os, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.models import IntelligenceCollection

c = IntelligenceCollection.objects.get(name='propiedades_propify')

print("=== CONFIGURACION DE COLECCION ===")
print(f"display_fields: {c.display_fields}")
print(f"display_fields type: {type(c.display_fields)}")
print()

fd = c.field_definitions
print(f"field_definitions type: {type(fd)}")
if isinstance(fd, dict):
    print(f"field_definitions keys: {list(fd.keys())}")
    for k, v in fd.items():
        print(f"  {k}: {v}")
elif isinstance(fd, list):
    print(f"field_definitions (list): {len(fd)} items")
    for item in fd[:5]:
        print(f"  {item}")
else:
    print(f"field_definitions raw: {fd}")
print()

# Verificar un documento de ejemplo
from intelligence.models import IntelligenceDocument
doc = IntelligenceDocument.objects.filter(collection=c).first()
if doc:
    fv = doc.field_values or {}
    print("=== PRIMER DOCUMENTO field_values (keys) ===")
    for k in sorted(fv.keys()):
        print(f"  {k}: {fv[k]}")
