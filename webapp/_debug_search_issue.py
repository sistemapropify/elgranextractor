import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
os.environ.setdefault('PROPIFAI_DB_NAME', 'dbpropify_be')
import django; django.setup()

from intelligence.models import IntelligenceDocument, IntelligenceCollection

# 1. Ver qué colecciones de propiedades existen
print("=== COLECCIONES ===")
colecciones = IntelligenceCollection.objects.filter(name__icontains='propiedad')
for c in colecciones:
    total = IntelligenceDocument.objects.filter(collection=c).count()
    con_embedding = IntelligenceDocument.objects.filter(collection=c, embedding__isnull=False).count()
    print(f"  {c.name}: total={total}, con_embedding={con_embedding}")
    # Ver field_values keys del primer doc
    primero = IntelligenceDocument.objects.filter(collection=c).first()
    if primero and primero.field_values:
        fv_keys = list(primero.field_values.keys())[:20]
        print(f"    field_values keys: {fv_keys}")

# 2. Buscar propiedades en Cercado
print("\n=== PROPIEDADES EN CERCADO ===")
for c in colecciones:
    docs = IntelligenceDocument.objects.filter(collection=c, embedding__isnull=False)
    cercado_docs = []
    for d in docs:
        fv = d.field_values or {}
        # Buscar en todos los campos de distrito
        for key in fv:
            val = str(fv[key]).lower() if fv[key] else ''
            if 'cercado' in val and ('district' in key.lower() or 'distrito' in key.lower()):
                cercado_docs.append((d.id, key, fv.get('title',''), fv.get(key,'')))
    if cercado_docs:
        print(f"  Colección {c.name}: {len(cercado_docs)} propiedades en Cercado")
        for d_id, key, title, val in cercado_docs[:10]:
            print(f"    [{d_id}] title={title}, {key}={val}")
    else:
        print(f"  Colección {c.name}: NO HAY propiedades en Cercado o no tienen district en field_values")

# 3. Ver valores únicos de district_name en field_values
print("\n=== DISTRITOS EN field_values ===")
distritos_vistos = set()
for c in colecciones:
    docs = IntelligenceDocument.objects.filter(collection=c, embedding__isnull=False)[:500]
    for d in docs:
        fv = d.field_values or {}
        for name_key in ['district_name', 'distrito', 'district']:
            val = fv.get(name_key)
            if val:
                distritos_vistos.add(str(val))

print(f"Distritos encontrados: {sorted(distritos_vistos)}")

# 4. Verificar con query semántica real
print("\n=== TEST SEMÁNTICO ===")
from intelligence.services.rag import RAGService

query = "propiedades en cercado de arequipa para negocio o gimnasio"
query_emb = RAGService.generate_embedding(query, mode='query')
if query_emb:
    import numpy as np
    qv = np.frombuffer(query_emb, dtype=np.float32)
    print(f"Query embedding generado: {qv.shape}")
    
    for c in colecciones:
        docs = IntelligenceDocument.objects.filter(collection=c, embedding__isnull=False)[:200]
        mejores = []
        for d in docs:
            if d.embedding:
                dv = np.frombuffer(d.embedding, dtype=np.float32)
                if dv.shape == qv.shape:
                    sim = float(np.dot(qv, dv) / (np.linalg.norm(qv) * np.linalg.norm(dv)))
                    fv = d.field_values or {}
                    title = fv.get('title', '')
                    district = fv.get('district_name', '')
                    mejores.append((sim, d.id, title, district))
        mejores.sort(key=lambda x: x[0], reverse=True)
        print(f"\n  Top 10 para colección '{c.name}':")
        for sim, did, title, dist in mejores[:10]:
            print(f"    score={sim:.4f} id={did} title={title[:40]} district={dist}")
