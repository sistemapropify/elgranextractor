# Tech Steering — PIL (PropiFai Intelligence Layer)

> **Purpose:** Technical architecture, standards, and key decisions for PIL evolution.
> **Status:** Active
> **Last Updated:** 2026-06-21

---

## Architecture Target: Multi-Agent System

```
+-----------------------------------------------------------+
|                    PIL ORCHESTRATOR                       |
|              (LangGraph StateGraph)                       |
+-----------------------------------------------------------+
                            |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
+---------------+   +---------------+   +---------------+
| ROUTER AGENT  |   | SEARCH AGENT  |   | CONTEXT AGENT |
+---------------+   +---------------+   +---------------+
| - Clasifica   |   | - RAG + FAISS |   | - Memoria     |
|   intención   |   | - Pre-filtro  |   |   episódica   |
| - Decide skill|   |   SQL         |   | - Memoria de  |
| - Extrae      |   | - Hybrid      |   |   hechos      |
|   parámetros  |   |   search      |   | - Contexto    |
|               |   | - Ranking     |   |   activo      |
+---------------+   +---------------+   +---------------+
        |                   |                   |
        +-------------------+-------------------+
                            |
                            v
                   +-----------------+
                   | FORMATTER AGENT |
                   +-----------------+
                   | - Genera        |
                   |   respuesta     |
                   |   natural       |
                   | - Incluye IDs   |
                   | - Formatea      |
                   |   resultados    |
                   +-----------------+
```

## Tech Stack

| Component | Current | Target | Notes |
|-----------|---------|--------|-------|
| Backend | Django + DRF | Django + DRF | Stay |
| Database | Azure SQL Server | Azure SQL Server | Stay |
| Vector DB | FAISS HNSWFlat | FAISS HNSWFlat | Stay |
| Embedding | multilingual-e5-large | multilingual-e5-large | 1024 dims |
| LLM | DeepSeek API | DeepSeek API (function calling) | Add tool support |
| Orchestration | Sequential pipeline | LangGraph StateGraph | **New** |
| Observability | None | Arize Phoenix / LangSmith | **New** |
| PDF | PyMuPDF (planned) | PyMuPDF | **New** |
| MCP | @modelcontextprotocol/sdk 0.6.x | Same | Stay |

## Key Technical Decisions

### KTD-001: Function Calling over Routing Manual
- **Decision:** DeepSeek decides which tools to invoke via function calling API
- **Rationale:** Elimina routing manual por keywords; el LLM entiende semántica
- **Impact:** Reemplaza SkillRegistry completamente

### KTD-002: LangGraph over Sequential Pipeline
- **Decision:** StateGraph para orquestación con branching condicional
- **Rationale:** Permite skip de nodos, loops, checkpointing, human-in-the-loop
- **Impact:** Reemplaza pipeline secuencial rígido en chat_processor.py

### KTD-003: Multi-Agent over Monolithic
- **Decision:** Agentes especializados (Router, Search, Context, Formatter)
- **Rationale:** Cada agente se optimiza independientemente; facilita testing
- **Impact:** Separar responsabilidades del monolítico ChatProcessor

### KTD-004: Observabilidad con Tracing
- **Decision:** Cada tool call y decisión se traza con IDs correlacionados
- **Rationale:** No se puede mejorar lo que no se puede ver
- **Impact:** Arize Phoenix o LangSmith integration

### KTD-005: Cache con Conversation ID
- **Decision:** Cache keys incluyen conversation_id
- **Rationale:** Previene fuga de datos entre sesiones
- **Impact:** Modificar SkillOrchestrator cache key

## Performance Budgets

| Operation | p95 Target | Current | Priority |
|-----------|-----------|---------|----------|
| Semantic routing | <100ms | N/A (new) | 🔴 |
| FAISS search (85 docs) | <50ms | <10ms | ✅ |
| FAISS search (5000+ docs) | <100ms | N/A (future) | 🟡 |
| Full chat response | <5s | ~3-4s | 🟡 |
| PDF ingest per page | <1s | N/A (new) | 🟡 |

## Principles

1. **Incremental, no reescritura** — Envolver, no reemplazar
2. **Medir antes y después** — Cada cambio con métricas
3. **Observabilidad primero** — Trazar cada decisión
4. **Skills atómicas** — Una cosa bien
5. **Fallbacks graceful** — Si falla una tool, el agente continúa
6. **Cost-aware** — Monitorear tokens, optimizar cache
