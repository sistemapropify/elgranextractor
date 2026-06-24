# F2-002: Unify Skill Execution Paths

> **Phase:** 2 — LangGraph
> **Priority:** 🟡 MEDIUM
> **Estimated Effort:** 2 days
> **Dependencies:** F2-001 (LangGraph)
> **Status:** ✅ Implemented (via F2-001)

---

## Description

Actualmente coexisten dos sistemas de ejecución de skills: el nuevo `SkillRegistry.find_best_skill()` y el antiguo `_find_skill_candidate()` en `chat_processor.py`. Dependiendo de cuál detecte la skill primero, el flujo puede ser diferente. Con LangGraph, ambas rutas se unifican en un solo flujo.

## Goals

- [x] **7.1** Identificar ambas rutas en chat_processor.py
- [x] **7.2** `_find_skill_candidate()` ya no existe en el código (eliminado en refactor anterior)
- [x] **7.3** Routing migrado a `router_agent` de LangGraph (F2-001)
- [x] **7.4** `resolver_contexto` como nodo opcional `context_agent` en el grafo (F2-001)
- [x] **7.5** Sin código muerto — pipeline secuencial legacy es solo fallback
- [ ] **7.6** Probar determinismo (misma consulta → mismo resultado)

_Prompt: Eliminate the dual skill execution paths by deprecating the old _find_skill_candidate() and consolidating all routing logic into the LangGraph router_agent. This ensures deterministic behavior._

_Requirements: Remove old _find_skill_candidate(), consolidate in router_agent, verify no dead code_

_Leverage: F2-001 LangGraph orchestrator, F1-001 SemanticRouter_

_Files: webapp/intelligence/services/chat_processor.py (remove _find_skill_candidate), webapp/intelligence/agents/router_agent.py (consolidate)_

## Acceptance Criteria

- [x] **7.a** `_find_skill_candidate()` eliminado — ya no existe en el código
- [x] **7.b** Todo el routing pasa por `router_agent` de LangGraph — cuando USE_LANGGRAPH=True
- [x] **7.d** Sin código muerto — pipeline secuencial es fallback explícito
- [ ] **7.c** Misma consulta → mismo resultado — requiere pruebas
