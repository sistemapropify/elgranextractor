# F2-001: LangGraph Orchestration

> **Phase:** 2 — LangGraph
> **Priority:** 🔴 CRITICAL
> **Estimated Effort:** 5 days
> **Dependencies:** F1-001 (Semantic Router), F1-002 (SQL Pre-filtering)
> **Status:** Pending

---

## Description

Reemplazar el pipeline secuencial rígido de `ChatProcessor.process_message()` por una orquestación con LangGraph StateGraph. Esto permite branching condicional (saltar resolver_contexto si es turno 1), loops (reintentar si resultados insuficientes), checkpointing (persistir estado) y human-in-the-loop.

## Goals

- [x] **6.1** Analizar flujo actual de `ChatProcessor.process_message()`
- [ ] **6.2** Definir `PILAgentState` TypedDict con todos los campos del estado
- [ ] **6.3** Implementar nodo `router_agent`: clasificar intención (usa SemanticRouter)
- [ ] **6.4** Implementar nodo `search_agent`: RAG + FAISS + SQL pre-filtering
- [ ] **6.5** Implementar nodo `context_agent`: memoria episódica + hechos + contexto activo
- [ ] **6.6** Implementar nodo `formatter_agent`: formatear respuesta con DeepSeek
- [ ] **6.7** Implementar conditional edges: saltar context_agent si no hay contexto previo
- [ ] **6.8** Implementar checkpointing del estado
- [ ] **6.9** Migrar `ChatProcessor.process_message()` a usar LangGraph
- [ ] **6.10** Agregar tracing de cada nodo y transición
- [ ] **6.11** Probar con casos: primer turno, follow-up, consulta sin match

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

- [ ] **6.a** StateGraph con 4 nodos implementados
- [ ] **6.b** Conditional edge: saltar context_agent si contexto_activo vacío
- [ ] **6.c** Checkpointing del estado entre turnos
- [ ] **6.d** Misma funcionalidad que el pipeline actual (sin regression)
- [ ] **6.e** Latencia no aumenta (debe mejorar por skip de context_agent)
- [ ] **6.f** Tracing de cada nodo ejecutado
