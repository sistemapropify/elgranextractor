# F2-002: Unify Skill Execution Paths

> **Phase:** 2 — LangGraph
> **Priority:** 🟡 MEDIUM
> **Estimated Effort:** 2 days
> **Dependencies:** F2-001 (LangGraph)
> **Status:** Pending

---

## Description

Actualmente coexisten dos sistemas de ejecución de skills: el nuevo `SkillRegistry.find_best_skill()` y el antiguo `_find_skill_candidate()` en `chat_processor.py`. Dependiendo de cuál detecte la skill primero, el flujo puede ser diferente. Con LangGraph, ambas rutas se unifican en un solo flujo.

## Goals

- [x] **7.1** Identificar ambas rutas en chat_processor.py (líneas 748-867)
- [ ] **7.2** Deprecar `_find_skill_candidate()` antiguo
- [ ] **7.3** Migrar toda la lógica de routing al `router_agent` de LangGraph
- [ ] **7.4** Migrar `resolver_contexto` como nodo opcional en el grafo
- [ ] **7.5** Verificar que no hay código muerto
- [ ] **7.6** Probar que misma consulta produce mismo resultado siempre

_Prompt: Eliminate the dual skill execution paths by deprecating the old _find_skill_candidate() and consolidating all routing logic into the LangGraph router_agent. This ensures deterministic behavior._

_Requirements: Remove old _find_skill_candidate(), consolidate in router_agent, verify no dead code_

_Leverage: F2-001 LangGraph orchestrator, F1-001 SemanticRouter_

_Files: webapp/intelligence/services/chat_processor.py (remove _find_skill_candidate), webapp/intelligence/agents/router_agent.py (consolidate)_

## Acceptance Criteria

- [ ] **7.a** `_find_skill_candidate()` eliminado
- [ ] **7.b** Todo el routing pasa por `router_agent` de LangGraph
- [ ] **7.c** Misma consulta → mismo resultado (determinista)
- [ ] **7.d** Sin código muerto ni imports huérfanos
