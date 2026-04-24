"""Debug: Ver datos reales de la coleccion propiedades_propify"""
import django, os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
os.environ['RAG_SIMILARITY_THRESHOLD'] = '0.2'
django.setup()

from intelligence.models import IntelligenceDocument, IntelligenceCollection

col = IntelligenceCollection.objects.filter(name='propiedades_propify').first()
if not col:
    print("NO EXISTE coleccion propiedades_propify")
    for c in IntelligenceCollection.objects.all():
        print(f"  {c.name}: active={c.is_active}")
    sys.exit(1)

total = IntelligenceDocument.objects.filter(collection=col).count()
print(f"Total docs en propiedades_propify: {total}")

docs = IntelligenceDocument.objects.filter(collection=col)[:5]
for d in docs:
    print(f"\n--- Doc {d.id} (source_id={d.source_id}) ---")
    fv = d.field_values or {}
    print(f"  Campos en field_values: {list(fv.keys())}")
    print(f"  titulo: {fv.get('titulo', 'NO_TITULO')}")
    print(f"  distrito: {fv.get('distrito', 'NO_DISTRITO')}")
    print(f"  direccion: {fv.get('direccion', 'NO_DIR')}")
    print(f"  precio: {fv.get('precio', 'NO_PRECIO')}")
    print(f"  tipo_propiedad: {fv.get('tipo_propiedad', 'NO_TIPO')}")
    print(f"  area_construida: {fv.get('area_construida', 'NO_AREA')}")
    print(f"  moneda: {fv.get('moneda', 'NO_MONEDA')}")
    print(f"  descripcion: {str(fv.get('descripcion', 'NO_DESC'))[:100]}")
    print(f"  embedding: {len(d.embedding) if d.embedding else 0} bytes")
