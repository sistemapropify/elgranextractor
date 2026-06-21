"""
Verificar si district_name existe en field_values del documento.
"""
import sys, os, django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.models import IntelligenceDocument, IntelligenceCollection

c = IntelligenceCollection.objects.get(name='propiedades_propify')

# Buscar el documento con source_id=1
doc = IntelligenceDocument.objects.filter(collection=c, source_id=1).first()
if doc:
    fv = doc.field_values or {}
    print(f"Documento source_id=1:")
    print(f"  'district_name' in fv: {'district_name' in fv}")
    print(f"  fv['district_name']: {fv.get('district_name', 'NOT FOUND')}")
    print(f"  'district_fk_id' in fv: {'district_fk_id' in fv}")
    print(f"  fv['district_fk_id']: {fv.get('district_fk_id', 'NOT FOUND')}")
    print(f"  'district' in fv: {'district' in fv}")
    print(f"  fv['district']: {fv.get('district', 'NOT FOUND')}")
    print()
    # Mostrar todas las keys que empiezan con district
    print("  Keys con 'district':")
    for k in sorted(fv.keys()):
        if 'district' in k.lower():
            print(f"    {k}: {fv[k]}")
    
    # Ahora probar _build_field_values_to_display
    from intelligence.services.rag import RAGService
    display_fv = RAGService._build_field_values_to_display(doc)
    print()
    print("  _build_field_values_to_display result:")
    print(f"    'district_name' in display_fv: {'district_name' in display_fv}")
    print(f"    display_fv['district_name']: {display_fv.get('district_name', 'NOT FOUND')}")
    print(f"    'district' in display_fv: {'district' in display_fv}")
    print(f"    display_fv['district']: {display_fv.get('district', 'NOT FOUND')}")
