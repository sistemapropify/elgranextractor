# F1-004: Add conversation_id to Cache Key

> **Phase:** 1 — Function Calling
> **Priority:** 🟡 MEDIUM
> **Estimated Effort:** 1 day
> **Dependencies:** None
> **Status:** ✅ Implemented (2026-06-21)

---

## Description

El cache key de `SkillOrchestrator` no incluye `conversation_id`, lo que significa que dos usuarios con los mismos parámetros reciben el mismo resultado cacheado. Esto puede causar fugas de información entre sesiones. Se debe agregar `conversation_id` al cache key.

## Goals

- [x] **4.1** Identificar caché en `SkillOrchestrator.execute_skill()`
- [x] **4.2** Modificar cache key para incluir `conversation_id` — [`_generate_cache_key()`](../webapp/intelligence/skills/orchestrator.py:528)
- [x] **4.3** Verificar que no hay otros caches sin conversation_id — único punto de generación de cache keys en orchestrator
- [ ] **4.4** Agregar test de aislamiento entre conversaciones (pendiente)
- [ ] **4.5** Documentar política de cache keys (pendiente)

_Prompt: Add conversation_id to the SkillOrchestrator cache key to prevent cross-session data leakage. The current cache only uses skill parameters, so two users with identical search params get cached results from other sessions._

_Requirements: Cache key = hash(skill_name + conversation_id + sorted(params)), verify no other caches miss conversation_id_

_Leverage: existing SkillOrchestrator._get_cache_key()_

_Files: webapp/intelligence/skills/orchestrator.py (modify ~line 80)_

## Current Code

```python
# ACTUAL — Sin conversation_id
cache_key = f"skill:{skill_name}:{json.dumps(params, sort_keys=True)}"
```

## Target Code

```python
# NUEVO — Con conversation_id
cache_key = f"skill:{skill_name}:{conversation_id}:{json.dumps(params, sort_keys=True)}"
```

## Acceptance Criteria

- [x] **4.a** Cache key incluye `conversation_id` — formato `skill:{name}:{conv_id}:{hash}`
- [x] **4.b** Dos conversaciones con mismos params NO comparten caché — conversation_id en hash + key prefix
- [x] **4.c** Misma conversación con mismos params SÍ usa caché — mismo conversation_id = mismo key
- [x] **4.d** Sin breaking changes en API — solo cambia generación interna de key
