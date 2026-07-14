"""
Diagnóstico baseline: mide la calidad actual de discriminación semántica.
Correr ANTES de aplicar cualquier fix, y de nuevo DESPUÉS de cada fase.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
os.environ['SKIP_HEAVY_INIT'] = '1'

import django
django.setup()

from intelligence.models import IntelligenceDocument
from intelligence.services.rag import RAGService
import numpy as np

CASOS_PRUEBA = [
    ("cabaña maria", "Cabaña Maria"),
    ("las orquideas", "Orquideas"),
    ("agrega la propiedad de las orquideas", "Orquideas"),
    ("agrega las orquideas al lienzo", "Orquideas"),
    ("departamento en cayma", None),
]

def coseno(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def get_title(doc):
    if hasattr(doc, 'titulo') and doc.titulo:
        return doc.titulo
    fv = doc.field_values or {}
    return str(fv.get('title', f'source_id={doc.source_id}'))

def main():
    docs = list(IntelligenceDocument.objects.filter(embedding__isnull=False))
    print(f"Total documentos con embedding: {len(docs)}")
    print(f"Modelo: multilingual-e5-small (384d)")
    print(f"Pooling ACTUAL: pooler_output (antes del fix)")
    print("=" * 80)

    for query, esperado in CASOS_PRUEBA:
        q_emb_bytes = RAGService.generate_embedding(query, mode='query')
        q_emb = np.frombuffer(q_emb_bytes, dtype=np.float32)
        scores = []
        for doc in docs:
            d_emb = np.frombuffer(doc.embedding, dtype=np.float32)
            scores.append((get_title(doc), coseno(q_emb, d_emb), doc.source_id))
        scores.sort(key=lambda x: -x[1])

        print(f"\nQUERY: '{query}'  (esperado contiene: {esperado})")
        print("-" * 60)
        for titulo, score, sid in scores[:10]:
            marca = " <<< ESPERADO" if esperado and esperado.lower() in titulo.lower() else ""
            print(f"  {score:.4f}  [{sid}] {titulo[:70]}{marca}")
        
        if esperado:
            pos = None
            for i, (titulo, score, sid) in enumerate(scores):
                if esperado.lower() in titulo.lower():
                    pos = i + 1
                    break
            if pos:
                print(f"  >>> Posicion del esperado en ranking: {pos} de {len(scores)}")
            else:
                print(f"  >>> NO SE ENCONTRO el esperado en el ranking")

if __name__ == "__main__":
    main()
