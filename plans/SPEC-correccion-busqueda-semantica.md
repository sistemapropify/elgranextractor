# SPEC: Corrección del sistema de búsqueda semántica — Propifai

**Prioridad:** Alta — bug funcional afecta toda búsqueda desde el canvas
**Módulos afectados:** `rag.py`, `skill.py`, `chat_processor.py`, `faiss_index.py`

## Orden de ejecución

1. **Fase 1** — Fix de pooling en `rag.py` + migración de embeddings existentes
2. **Fase 2** — Limpieza de ruido en `semantic_query`
3. **Fase 3** — Fuzzy fallback (Estrategia 3)
4. **Fase 4** — Umbral de similitud calibrado
5. **Fase 5** — `top_k` configurado explícitamente
6. **Fase 6** — Tests de regresión

(Ver contenido completo en el mensaje del usuario)
