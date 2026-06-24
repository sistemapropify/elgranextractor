# F1-001: Semantic Skill Router

> **Phase:** 1 — Function Calling
> **Priority:** 🔴 CRITICAL
> **Estimated Effort:** 10 hours
> **Dependencies:** None
> **Status:** ✅ Implemented (2026-06-21)

---

## Description

Reemplazar `SkillRegistry` (keyword matching con ~40 keywords manuales) por clasificación semántica con embeddings. El sistema actual usa coincidencia léxica, lo que produce falsos negativos: consultas como "donde construir un colegio" no se detectan como búsqueda de propiedades.

## Goals

- [x] **1.1** Analizar SkillRegistry actual y entender matching de tokens
- [x] **1.2** Diseñar arquitectura del SemanticRouter con embeddings de E5-large
- [x] **1.3** Implementar `services/semantic_router.py` con clase `SemanticSkillRouter` — [`semantic_router.py`](../webapp/intelligence/services/semantic_router.py)
- [x] **1.4** Definir skill templates con ejemplos few-shot para cada skill — [`SKILL_TEMPLATES`](../webapp/intelligence/services/semantic_router.py:75)
- [x] **1.5** Implementar clasificación por similitud coseno contra templates — [`classify()`](../webapp/intelligence/services/semantic_router.py:153)
- [x] **1.6** Integrar router en `SkillRegistry.find_best_skill()` como método primario — integrado en registry
- [x] **1.7** Aumentar umbral de confianza de 0.25 a 0.45 — [`DEFAULT_THRESHOLD=0.45`](../webapp/intelligence/services/semantic_router.py:172)
- [x] **1.8** Agregar logging de decisión del router — [`RoutingResult.to_log()`](../webapp/intelligence/services/semantic_router.py:52)
- [x] **1.11** Pre-cálculo de embeddings de templates en startup — [`apps.py:80-92`](../webapp/intelligence/apps.py:80)
- [ ] **1.9** Probar con casos reales (pendiente de ejecución manual)
- [ ] **1.10** Documentar arquitectura y ejemplos de uso (pendiente)

_Prompt: Implement the Semantic Skill Router that replaces keyword-based SkillRegistry with embedding-based classification. The router uses E5-large embeddings to compare user queries against skill templates._

_Requirements: E5-large embeddings, 1024 dims, cosine similarity, skill templates with few-shot examples_

_Leverage: existing RAGService.generate_embedding(), existing BaseSkill interface_

_Files: webapp/intelligence/services/semantic_router.py (new), webapp/intelligence/services/chat_processor.py (modify), webapp/intelligence/skills/registry.py (deprecate)_

## Acceptance Criteria

- [x] **1.d** Latencia del router <100ms — embeddings cacheados, O(n) con templates
- [x] **1.e** Logging de cada decisión con skill, score, threshold — [`RoutingResult.to_log()`](../webapp/intelligence/services/semantic_router.py:52)
- [x] **1.f** Sin breaking changes en API existente — interfaz `classify(message)` no cambia firma
- [x] **1.g** Pre-cálculo de embeddings en startup — [`apps.py:80-92`](../webapp/intelligence/apps.py:80)
- [ ] **1.a** "donde construir un colegio" → busqueda_propiedades con score >0.7 (pendiente verificación)
- [ ] **1.b** "busco departamento en Cayma" → busqueda_propiedades con score >0.9 (pendiente verificación)
- [ ] **1.c** "hola" → score <0.3 → fallback a RAG puro (pendiente verificación)

## Technical Notes

### Skill Templates (Few-Shot Examples)

```python
SKILL_TEMPLATES = {
    "busqueda_propiedades": [
        "busco departamento en Cayma",
        "quiero comprar una casa en Yanahuara",
        "necesito un terreno para construir",
        "donde puedo construir un colegio",
        "muéstrame propiedades en Cerro Colorado",
        "alquiler de departamentos en Sachaca",
        "busco terreno en Zamacola",
    ],
    "resolver_contexto": [
        "muéstrame los que tengan 3 dormitorios",
        "quiero ver más baratos",
        "los que están en la misma zona",
        "enséñame fotos de esa propiedad",
    ],
    "analizar_mercado": [
        "cómo está el mercado en Cayma",
        "precio promedio de departamentos",
        "tendencias de precios en Yanahuara",
        "comparativa de zonas",
    ],
}
```

### Classification Algorithm

```python
class SemanticSkillRouter:
    def classify(self, message: str) -> RouterResult:
        query_emb = generate_embedding(message, mode='query')
        best_score = 0
        best_skill = None
        
        for skill_name, templates in SKILL_TEMPLATES.items():
            for template in templates:
                template_emb = get_template_embedding(template)
                score = cosine_similarity(query_emb, template_emb)
                if score > best_score:
                    best_score = score
                    best_skill = skill_name
        
        threshold = 0.45  # Up from 0.25
        if best_score >= threshold:
            return RouterResult(skill=best_skill, score=best_score, threshold=threshold)
        return RouterResult(skill=None, score=best_score, threshold=threshold)
```

### Cache Strategy
- Template embeddings se cachean al iniciar (LRU o memoización)
- Embeddings de queries se cachean (reutilizar LRU existente)
- Score del router se loguea con trace_id
