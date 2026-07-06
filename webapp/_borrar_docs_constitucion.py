"""
Script para borrar documentos viejos de la Constitucion (solo 1806 chars)
Ejecucion automatica (no interactiva).
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from intelligence.models import IntelligenceDocument, IntelligenceCollection

col = IntelligenceCollection.objects.filter(name='normativas_legales').first()
if not col:
    print("ERROR: Coleccion 'normativas_legales' no encontrada")
    sys.exit(1)

# Buscar documentos del PDF con hash especifico
docs = IntelligenceDocument.objects.filter(
    collection=col,
    source_id__startswith='pdf_5f6392be'
)
count = docs.count()
print(f"Documentos con hash 5f6392be: {count}")

if count > 0:
    docs.delete()
    print(f"{count} documentos borrados. Listo para re-subir con OCR.")
else:
    print("No se encontraron documentos con ese hash.")
    # Mostrar los que hay
    total = IntelligenceDocument.objects.filter(collection=col).count()
    print(f"Total documentos en coleccion: {total}")
