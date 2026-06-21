import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument

c = IntelligenceCollection.objects.get(name='propiedades_propify')

# Buscar documentos que contengan nombres de distrito en el contenido
docs = IntelligenceDocument.objects.filter(collection=c)[:10]
print("=== PRIMEROS 10 DOCUMENTOS (buscando district_name) ===")
for d in docs:
    fv = d.field_values or {}
    district_name = fv.get('district_name', 'NO TIENE')
    district_id = fv.get('district', 'N/A')
    title = fv.get('title', 'SIN TITULO')[:60]
    # Ver si el contenido incluye el nombre del distrito
    has_district = 'Cayma' in d.content or 'Cerro' in d.content or 'Yanahuara' in d.content
    print(f'  source_id={d.source_id}, title={title}')
    print(f'    district_id={district_id}, district_name={district_name}')
    print(f'    content incluye nombre distrito: {has_district}')
    print(f'    content[:200]: {d.content[:200]}')
    print('---')

print("\n=== BUSCANDO 'Yanahuara' EN CONTENIDO ===")
yanahuara_docs = [d for d in IntelligenceDocument.objects.filter(collection=c) if 'Yanahuara' in (d.content or '')]
print(f'Documentos con Yanahuara: {len(yanahuara_docs)}')
for d in yanahuara_docs[:5]:
    fv = d.field_values or {}
    print(f'  source_id={d.source_id}, title={fv.get("title", "?")}, district_name={fv.get("district_name", "?")}')

print("\n=== BUSCANDO 'Cayma' EN CONTENIDO ===")
cayma_docs = [d for d in IntelligenceDocument.objects.filter(collection=c) if 'Cayma' in (d.content or '')]
print(f'Documentos con Cayma: {len(cayma_docs)}')
for d in cayma_docs[:5]:
    fv = d.field_values or {}
    print(f'  source_id={d.source_id}, title={fv.get("title", "?")}, district_name={fv.get("district_name", "?")}')
