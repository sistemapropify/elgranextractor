# F3-002: Rate Limiting

> **Phase:** 3 — Observability
> **Priority:** 🟡 MEDIUM
> **Estimated Effort:** 2 days
> **Dependencies:** None
> **Status:** Pending

---

## Description

No hay control de cuántas veces un usuario puede ejecutar skills costosas (búsqueda semántica), lo que representa un riesgo de abuso y costo elevado. Implementar rate limiting por skill y por usuario.

## Goals

- [x] **10.1** Analizar patrones de uso actuales
- [ ] **10.2** Implementar `services/rate_limiter.py` con clase `RateLimiter`
- [ ] **10.3** Definir límites: N requests por minuto/hora/día por skill
- [ ] **10.4** Implementar storage de contadores (Redis o DB)
- [ ] **10.5** Integrar rate limiter en LangGraph orchestrator
- [ ] **10.6** Agregar logging de rate limit hits
- [ ] **10.7** Probar con burst de requests

_Prompt: Implement rate limiting per skill and per user to control operational costs and prevent abuse. Use Redis for distributed counting or DB fallback._

_Requirements: per-skill limits, per-user limits, configurable windows (minute/hour/day), Redis/DB storage_

_Leverage: existing Django cache framework or Redis_

_Files: webapp/intelligence/services/rate_limiter.py (new), webapp/intelligence/agents/orchestrator.py (integrate)_

## Rate Limits (Proposed)

| Skill | Limit | Window |
|-------|-------|--------|
| buscar_propiedades | 30 | por minuto |
| resolver_contexto | 60 | por minuto |
| analizar_mercado | 10 | por minuto |
| LLM (generación) | 20 | por minuto |
| Embeddings | 100 | por minuto |

## Acceptance Criteria

- [ ] **10.a** Rate limiting funcional por skill y usuario
- [ ] **10.b** Configuración de límites en settings.py
- [ ] **10.c** Respuesta HTTP 429 cuando se excede el límite
- [ ] **10.d** Logging de cada rate limit hit
- [ ] **10.e** Tests de burst de requests
