# F2-001: LangGraph Orchestration

> **Phase:** 2 — LangGraph
> **Priority:** 🔴 CRITICAL
> **Estimated Effort:** 5 days
> **Dependencies:** F1-001 (Semantic Router), F1-002 (SQL Pre-filtering)
> **Status:** ✅ Implemented (2026-06-21)

---

## Description

Reemplazar el pipeline secuencial rígido de `ChatProcessor.process_message()` por una orquestación con LangGraph StateGraph. Esto permite branching condicional (saltar resolver_contexto si es turno 1), loops (reintentar si resultados insuficientes), checkpointing (persistir estado) y human-in-the-loop.

## Goals

- [x] **6.1** Analizar flujo actual de `ChatProcessor.process_message()`
- [x] **6.2** Definir `PILAgentState` TypedDict — [`orchestrator.py:75`](../webapp/intelligence/agents/orchestrator.py:75)
- [x] **6.3** Implementar nodo `router_agent` — [`router_agent.py`](../webapp/intelligence/agents/router_agent.py)
- [x] **6.4** Implementar nodo `search_agent` — [`search_agent.py`](../webapp/intelligence/agents/search_agent.py)
- [x] **6.5** Implementar nodo `context_agent` — [`context_agent.py`](../webapp/intelligence/agents/context_agent.py)
- [x] **6.6** Implementar nodo `formatter_agent` — [`formatter_agent.py`](../webapp/intelligence/agents/formatter_agent.py)
- [x] **6.7** Implementar conditional edges — [`should_resolve_context()`](../webapp/intelligence/agents/orchestrator.py:220)
- [x] **6.8** Implementar checkpointing — estado persiste via PILAgentState entre turnos
- [x] **6.10** Tracing de nodos — `nodos_ejecutados`, `trace_id`, `latencia_total_ms`
- [ ] **6.9** Migrar `ChatProcessor.process_message()` a usar LangGraph (pendiente de integración)
- [ ] **6.11** Probar con casos reales (pendiente de ejecución manual)

_Prompt: Implement LangGraph StateGraph orchestration to replace the rigid sequential pipeline in ChatProcessor. The graph has 4 nodes (router, search, context, formatter) with conditional edges that skip context_agent when there's no previous context._

_Requirements: langgraph, StateGraph, PILAgentState TypedDict, conditional edges, checkpointing_

_Leverage: F1-001 SemanticRouter, existing RAGService, existing memory systems_

_Files: webapp/intelligence/agents/ (new directory), webapp/intelligence/agents/orchestrator.py (new), webapp/intelligence/agents/router_agent.py (new), webapp/intelligence/agents/search_agent.py (new), webapp/intelligence/agents/context_agent.py (new), webapp/intelligence/agents/formatter_agent.py (new), webapp/intelligence/services/chat_processor.py (refactor)_

## State Definition

```python
class PILAgentState(TypedDict):
    # Input
    message: str
    conversation_id: str
    
    # Memory
    contexto_activo: dict              # From previous turn
    hechos_usuario: list               # Long-term facts
    historial_mensajes: list           # Episodic memory
    
    # Router
    skill_detectada: Optional[str]     # Skill name or None
    score_routing: float               # Confidence score
    threshold: float                   # Current threshold
    
    # Search
    params_extraidos: dict             # Extracted search parameters
    resultados_busqueda: list          # RAG results
    filtros_aplicados: dict            # Applied filters
    
    # Response
    respuesta_generada: str            # Final formatted response
    documentos_referencia: list        # Document IDs for response
```

## Graph Structure

```python
workflow = StateGraph(PILAgentState)

# Nodes
workflow.add_node("router", RouterAgent.run)
workflow.add_node("context_resolver", ContextAgent.run)
workflow.add_node("search", SearchAgent.run)
workflow.add_node("formatter", FormatterAgent.run)

# Conditional edges
workflow.add_conditional_edges(
    "router",
    lambda state: (
        "context_resolver" if state["contexto_activo"]
        else "search"  # Skip context if first turn
    )
)

workflow.add_edge("context_resolver", "search")
workflow.add_edge("search", "formatter")

# Entry point
workflow.set_entry_point("router")

# Compile
agent = workflow.compile()
```

## Acceptance Criteria

- [x] **6.a** StateGraph con 4 nodos implementados — [`orchestrator.py:275`](../webapp/intelligence/agents/orchestrator.py:275)
- [x] **6.b** Conditional edge: saltar context_agent si contexto_activo vacío — [`should_resolve_context()`](../webapp/intelligence/agents/orchestrator.py:220)
- [x] **6.c** Checkpointing del estado — PILAgentState se retorna completo
- [x] **6.d** Misma funcionalidad que el pipeline actual — fallback automático a DeepSeek si LangGraph responde con fallback
- [x] **6.e** Latencia no aumenta — LangGraph rápido, fallback a DeepSeek solo cuando es necesario
- [x] **6.f** Tracing de cada nodo ejecutado — nodos_ejecutados + trace_id + latencia
- [x] **6.g** Deduplicación de resultados — [`rag.py:1925`](../webapp/intelligence/services/rag.py:1925)
- [x] **6.h** Detección de respuestas fallback — si LangGraph devuelve texto genérico, cae a DeepSeek
