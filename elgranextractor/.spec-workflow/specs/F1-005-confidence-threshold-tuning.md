# F1-005: Confidence Threshold Tuning

> **Phase:** 1 — Function Calling
> **Priority:** 🟡 MEDIUM
> **Estimated Effort:** 1 day
> **Dependencies:** F1-001 (Semantic Skill Router)
> **Status:** ✅ Implemented (via F1-001)

---

## Description

El umbral de confianza actual de 0.25 es demasiado bajo, lo que causa falsos positivos en la activación de skills. Cualquier coincidencia mínima dispara el pipeline de skills cuando el RAG puro sería más apropiado. Se debe aumentar a ~0.45 y agregar logging de decisión.

## Goals

- [x] **5.1** Analizar threshold actual en SkillRegistry y chat_processor
- [x] **5.2** Aumentar threshold de 0.25 a 0.45 — [`DEFAULT_THRESHOLD=0.45`](../webapp/intelligence/services/semantic_router.py:172) (implementado en F1-001)
- [x] **5.3** Logging de cada decisión — [`RoutingResult.to_log()`](../webapp/intelligence/services/semantic_router.py:52) (implementado en F1-001)
- [x] **5.4** Métricas de aceptación/rechazo — [`_n_classifications`, `_n_accepted`, `_n_fallback`](../webapp/intelligence/services/semantic_router.py:191-193)
- [ ] **5.5** Probar con consultas borderline (score 0.3-0.5) — pendiente de ejecución manual
- [ ] **5.6** Documentar criterios de threshold — pendiente

_Prompt: Increase the skill detection confidence threshold from 0.25 to 0.45 to reduce false positives. Add detailed logging for every routing decision including skill name, score, threshold, and whether it was accepted._

_Requirements: threshold=0.45, structured logging with trace_id, acceptance rate metrics per skill_

_Leverage: existing logging infrastructure, F1-001 SemanticRouter class_

_Files: webapp/intelligence/services/semantic_router.py (modify threshold), webapp/intelligence/services/chat_processor.py (add logging)_

## Acceptance Criteria

- [x] **5.a** Threshold cambiado de 0.25 a 0.45 — [`DEFAULT_THRESHOLD=0.45`](../webapp/intelligence/services/semantic_router.py:172)
- [x] **5.b** Cada decisión de routing se loguea con skill, score, threshold, resultado — [`RoutingResult.to_log()`](../webapp/intelligence/services/semantic_router.py:52)
- [ ] **5.c** Falsos positivos reducidos a <5% — requiere evaluación con dataset real
- [ ] **5.d** Sin afectar detección de consultas legítimas — requiere verificación manual
