# F2-003: Optimize resolver_contexto

> **Phase:** 2 — LangGraph
> **Priority:** 🟢 LOW
> **Estimated Effort:** 1 day
> **Dependencies:** F2-001 (LangGraph conditional edges)
> **Status:** Pending

---

## Description

El pipeline secuencial ejecuta `resolver_contexto` innecesariamente incluso cuando no hay contexto previo (primer turno), añadiendo ~200-500ms extra por request. Con LangGraph, esto se soluciona con un conditional edge que salta el nodo si el contexto_activo está vacío.

## Goals

- [x] **8.1** Analizar _get_contexto_activo() en chat_processor.py
- [x] **8.2** Conditional edge ya implementado en F2-001 (LangGraph)
- [ ] **8.3** Verificar que resolver_contexto se salta en primer turno
- [ ] **8.4** Resolver problema de dos fuentes de verdad (metadata vs SkillExecution)
- [ ] **8.5** Unified context source: solo `conversation.metadata`

_Prompt: Skip resolver_contexto execution when there's no previous context (first turn). This is already handled by LangGraph conditional edges from F2-001. Also resolve the dual source of truth issue between conversation.metadata and SkillExecution.parameters._

_Requirements: Conditional edge check, unified context source in conversation.metadata only_

_Leverage: F2-001 LangGraph conditional edges_

_Files: webapp/intelligence/agents/context_agent.py (optimize), webapp/intelligence/services/chat_processor.py (cleanup _get_contexto_activo)_

## Acceptance Criteria

- [ ] **8.a** resolver_contexto NO se ejecuta en primer turno (contexto_activo vacío)
- [ ] **8.b** Fuente única de verdad: `conversation.metadata['contexto_activo_busqueda']`
- [ ] **8.c** Latencia reducida ~200-500ms en primeros turnos
- [ ] **8.d** `_get_contexto_activo()` usa `refresh_from_db()` para evitar datos stale
