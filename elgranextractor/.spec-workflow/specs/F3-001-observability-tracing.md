# F3-001: Observability & Tracing

> **Phase:** 3 — Observability
> **Priority:** 🔴 CRITICAL
> **Estimated Effort:** 3 days
> **Dependencies:** F2-001 (LangGraph nodes to trace)
> **Status:** Pending

---

## Description

Implementar observabilidad completa del sistema PIL con tracing de cada tool call, decisión de routing, búsqueda RAG y formateo de respuesta. Actualmente solo se loguea "éxito" o "error" sin detalles de documentos específicos recuperados.

## Goals

- [x] **9.1** Analizar logging actual en skill.py (solo éxito/error)
- [ ] **9.2** Implementar tracing con trace_id por request
- [ ] **9.3** Agregar logging de documentos RAG: IDs y scores recuperados
- [ ] **9.4** Agregar logging de decisiones del SemanticRouter
- [ ] **9.5** Agregar logging de ejecución de cada nodo LangGraph
- [ ] **9.6** Agregar IDs de documento en prompt de DeepSeek (para que el usuario pueda ver detalles)
- [ ] **9.7** Implementar dashboard de métricas básicas
- [ ] **9.8** Documentar formato de logs y cómo consultarlos

_Prompt: Implement full observability with trace_id correlation across all PIL components. Log every routing decision, RAG document retrieved (with IDs and scores), LangGraph node execution, and DeepSeek interaction. Include document IDs in the DeepSeek prompt so users can access property details._

_Requirements: trace_id per request, structured JSON logging, RAG document-level logging, document IDs in prompt_

_Leverage: existing logging infrastructure, LangGraph node callbacks_

_Files: webapp/intelligence/services/tracing.py (new), webapp/intelligence/agents/*.py (add tracing), webapp/intelligence/skills/propiedades/skill.py (add doc logging), webapp/intelligence/services/chat_processor.py (add doc IDs to prompt)_

## Tracing Architecture

```python
# Tracing context per request
class TraceContext:
    trace_id: str
    start_time: datetime
    nodes_executed: List[NodeTrace]
    router_decisions: List[RouterDecision]
    rag_documents: List[DocumentTrace]
    
class NodeTrace:
    node_name: str
    duration_ms: float
    status: str  # success/error/skipped
    input_summary: str
    output_summary: str
    
class RouterDecision:
    skill_name: Optional[str]
    score: float
    threshold: float
    accepted: bool
    
class DocumentTrace:
    document_id: int
    score: float
    collection: str
    source_id: str
```

## Acceptance Criteria

- [ ] **9.a** Cada request tiene trace_id único correlacionado
- [ ] **9.b** Logging de cada documento RAG: ID, score, collection
- [ ] **9.c** Logging de cada decisión de routing: skill, score, threshold
- [ ] **9.d** Logging de cada nodo LangGraph ejecutado: nombre, duración, estado
- [ ] **9.e** Prompt de DeepSeek incluye IDs de documento
- [ ] **9.f** Dashboard o consulta de logs estructurados
