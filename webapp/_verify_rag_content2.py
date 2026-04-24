import django, os, json, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import IntelligenceCollection, IntelligenceDocument

c = IntelligenceCollection.objects.get(name='propiedades_propify')

# Buscar documentos que contengan nombres de distrito en field_values
docs = IntelligenceDocument.objects.filter(collection=c)[:5]
output = []
output.append("=== PRIMEROS 5 DOCUMENTOS ===")
for d in docs:
    fv = d.field_values or {}
    district_name = fv.get('district_name', 'NO TIENE')
    district_id = fv.get('district', 'N/A')
    title = str(fv.get('title', 'SIN TITULO'))[:60]
    output.append(f'source_id={d.source_id}, title={title}')
    output.append(f'  district_id={district_id}, district_name={district_name}')
    output.append(f'  content[:200]: {str(d.content[:200])}')
    output.append('---')

output.append("\n=== BUSCANDO 'Yanahuara' EN field_values ===")
all_docs = IntelligenceDocument.objects.filter(collection=c)
yanahuara_docs = []
for d in all_docs:
    fv = d.field_values or {}
    dn = fv.get('district_name', '')
    if 'Yanahuara' in str(dn):
        yanahuara_docs.append(d)
output.append(f'Documentos con Yanahuara: {len(yanahuara_docs)}')
for d in yanahuara_docs[:5]:
    fv = d.field_values or {}
    output.append(f'  source_id={d.source_id}, title={fv.get("title", "?")}, district_name={fv.get("district_name", "?")}')

output.append("\n=== BUSCANDO 'Cayma' EN field_values ===")
cayma_docs = []
for d in all_docs:
    fv = d.field_values or {}
    dn = fv.get('district_name', '')
    if 'Cayma' in str(dn):
        cayma_docs.append(d)
output.append(f'Documentos con Cayma: {len(cayma_docs)}')
for d in cayma_docs[:5]:
    fv = d.field_values or {}
    output.append(f'  source_id={d.source_id}, title={fv.get("title", "?")}, district_name={fv.get("district_name", "?")}')

# Escribir a archivo para evitar problemas de encoding
with open('_rag_verify_output.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print("Output escrito en _rag_verify_output.txt")
