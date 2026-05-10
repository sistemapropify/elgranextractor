import sys, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
import django
django.setup()

from intelligence.models import IntelligenceDocument, IntelligenceCollection

c = IntelligenceCollection.objects.get(name='propiedades_propify')
total = IntelligenceDocument.objects.filter(collection=c).count()
con_vec = IntelligenceDocument.objects.filter(collection=c).exclude(embedding__isnull=True).count()

print(f"Total documentos: {total}")
print(f"Con embedding (vector): {con_vec}")
print(f"Sin embedding: {total - con_vec}")
print()

docs = IntelligenceDocument.objects.filter(collection=c).order_by('?')[:5]
print("=== MUESTRA DE 5 DOCS ALEATORIOS ===")
for d in docs:
    size = len(d.embedding) if d.embedding else 0
    fv = d.field_values or {}
    title = fv.get('title', 'N/A')[:50]
    district = fv.get('district_name', 'N/A')
    print(f"  ID={d.id} | source={d.source_id} | Vector: {'SI' if d.embedding else 'NO'} ({size} bytes) | {district} | {title}")
