# SPEC: Corrección del sistema de búsqueda semántica — Propifai

**Prioridad:** Alta — bug funcional afecta toda búsqueda desde el canvas
**Módulos afectados:** `rag.py`, `skill.py`, `chat_processor.py`, `faiss_index.py`
**Regla de oro:** aplicar las fases EN ORDEN. La Fase 1 invalida los embeddings existentes; si se aplican las fases 2-5 antes de terminar la Fase 1, el sistema quedará en un estado mixto e inconsistente (embeddings viejos y nuevos en el mismo espacio vectorial, no comparables entre sí).

---

## FASE 0 — Diagnóstico previo (no tocar código todavía)

Antes de cambiar nada, correr este script y guardar el output como baseline.

**Archivo nuevo:** `scripts/diagnostico_embeddings.py`

```python
"""
Diagnóstico baseline: mide la calidad actual de discriminación semántica.
Correr ANTES de aplicar cualquier fix, y de nuevo DESPUÉS de cada fase,
para verificar que cada cambio mejora (o al menos no empeora) los resultados.
"""
import django
django.setup()

from intelligence.models import IntelligenceDocument
from intelligence.services.rag import RAGService
import numpy as np

CASOS_PRUEBA = [
    ("cabaña maria", "Cabaña Maria"),
    ("las orquideas", "Orquideas"),
    ("agrega la propiedad de las orquideas", "Orquideas"),
    ("departamento en cayma", None),
]

def coseno(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def main():
    docs = list(IntelligenceDocument.objects.filter(embedding__isnull=False))
    print(f"Total documentos con embedding: {len(docs)}\n")

    for query, esperado in CASOS_PRUEBA:
        q_emb = np.frombuffer(RAGService.generate_embedding(query, mode='query'), dtype=np.float32)
        scores = []
        for doc in docs:
            d_emb = np.frombuffer(doc.embedding, dtype=np.float32)
            scores.append((doc.titulo if hasattr(doc, 'titulo') else doc.field_values.get('title',''), coseno(q_emb, d_emb)))
        scores.sort(key=lambda x: -x[1])

        print(f"QUERY: '{query}'  (esperado: {esperado})")
        for titulo, score in scores[:5]:
            marca = " <-- ESPERADO" if esperado and esperado.lower() in titulo.lower() else ""
            print(f"    {score:.4f}  {titulo}{marca}")
        if esperado:
            for i, (titulo, score) in enumerate(scores):
                if esperado.lower() in titulo.lower():
                    print(f"    -> posicion en ranking: {i+1} de {len(scores)}")
                    break
        print()

if __name__ == "__main__":
    main()
```

**Acción:** ejecutar y guardar el output completo en `docs/diagnostico_baseline.txt`.

---

## FASE 1 — Corregir el pooling del embedding (CRÍTICO, hacer primero)

### 1.1 Diagnóstico del problema

`multilingual-e5-small` es un modelo XLM-RoBERTa fine-tuneado para retrieval usando **mean pooling enmascarado + normalización L2**, NO `pooler_output`. El `pooler_output` de un RoBERTa es una capa densa+tanh sobre el token `[CLS]` que típicamente no participa del objetivo de entrenamiento contrastivo de E5. Usar `pooler_output` produce embeddings de menor calidad discriminativa.

### 1.2 Archivo a modificar

`webapp/intelligence/services/rag.py`

### 1.3 Código actual (a reemplazar)

```python
@classmethod
def generate_embedding(cls, text, mode='query'):
    prefixed = f"{'query' if mode == 'query' else 'passage'}: {text}"
    tokens = tokenizer(prefixed, return_tensors='pt', ...)
    with torch.no_grad():
        embedding = model(**tokens).pooler_output
    return embedding.numpy().tobytes()
```

### 1.4 Código corregido

```python
import torch
import torch.nn.functional as F

def _average_pool(last_hidden_states, attention_mask):
    mask_expanded = attention_mask[..., None].bool()
    last_hidden = last_hidden_states.masked_fill(~mask_expanded, 0.0)
    return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]

@classmethod
def generate_embedding(cls, text, mode='query'):
    prefixed = f"{'query' if mode == 'query' else 'passage'}: {text}"
    tokens = cls.tokenizer(
        prefixed,
        return_tensors='pt',
        padding=True,
        truncation=True,
        max_length=512,
    )
    with torch.no_grad():
        output = cls.model(**tokens)
    embedding = _average_pool(output.last_hidden_state, tokens['attention_mask'])
    embedding = F.normalize(embedding, p=2, dim=1)
    return embedding.squeeze(0).numpy().astype('float32').tobytes()
```

### 1.5 Migración obligatoria: regenerar TODOS los embeddings existentes

**Script:** `scripts/migrar_embeddings_v2.py`

### 1.6 Criterio de aceptación

Correr de nuevo `diagnostico_embeddings.py` y comparar contra baseline: score del documento esperado debe subir de posición, gap debe ser mayor.

---

## FASE 2 — Limpiar el `semantic_query` antes de generar el embedding

### 2.1 Archivo a modificar

`webapp/intelligence/skills/propiedades/skill.py`, dentro de `execute()`.

### 2.2 Regla de precedencia

1. Si `titulo_contains` fue detectado → usarlo tal cual
2. Si no → Estrategia 3 (fuzzy)
3. Si Estrategia 3 tampoco encuentra → limpieza de ruido

### 2.3 Código

```python
PALABRAS_RUIDO = {
    'agrega', 'agregue', 'añade', 'anade', 'pon', 'metelo', 'mételo', 'trae',
    'busca', 'encuentra', 'muestra', 'muestrame', 'muéstrame', 'lista', 'quiero',
    'al', 'del', 'en', 'para', 'por',
    'lienzo', 'canvas',
    'favor', 'gracias', 'hola', 'porfa', 'porfavor',
}
```

---

## FASE 3 — Agregar Estrategia 3: fuzzy matching como fallback

Dependencia: `rapidfuzz`

---

## FASE 4 — Umbral de similitud mínima (calibrado con datos)

Se calibra DESPUÉS de Fase 1 (cambio de pooling altera los scores).

---

## FASE 5 — Configurar `top_k` real desde el canvas

Default bajar de 999 a 10. Canvas usar top_k=5.

---

## FASE 6 — Tests de regresión

`intelligence/tests/test_busqueda_semantica.py`
