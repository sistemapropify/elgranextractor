# PIL (PropiFai Intelligence Layer) — Visión Arquitectónica

> **Documento fuente de verdad para la evolución de PIL hacia un sistema multi-agente completo.**
> **Versión:** 2.0 — Junio 2026
> **Propósito:** Contexto fundamental para MCP, desarrollo y referencia arquitectónica
> **Estado:** ✅ Actualizado con implementaciones hasta F5-001

---

## 1. VISIÓN

PIL es un sistema multi-agente especializado en el dominio inmobiliario que ha evolucionado desde un sistema de skills clásico hacia una arquitectura agentica completa implementada con LangGraph. La potencia del sistema no radica en el LLM (DeepSeek), sino en las skills/tools que puede invocar y en cómo las orquesta.

**OBJETIVO FINAL:** PIL será un sistema completo capaz de:
- Entender requerimientos complejos en lenguaje natural
- Razonar sobre qué acciones ejecutar
- Coordinar múltiples agentes especializados
- Aprender de cada interacción
- Ejecutar tareas complejas de extremo a extremo

**ESTADO ACTUAL:** 75% — Arquitectura multi-agente operativa con LangGraph, Semantic Router, sistema RAG, memorias y evaluación.

---

## 2. ESTADO ACTUAL (75%)

### Componentes Implementados

| # | Componente | Archivo | Función | Estado |
|---|---|---|---|---|
| 1 | **SemanticSkillRouter** (F1-001) | [`services/semantic_router.py`](webapp/intelligence/services/semantic_router.py) | Routing semántico de skills con embeddings E5-large y similitud coseno. Reemplaza keyword matching. | ✅ Producción |
| 2 | **PILOrchestrator** (F2-001) | [`agents/orchestrator.py`](webapp/intelligence/agents/orchestrator.py) | Orquestador multi-agente con LangGraph StateGraph. 4 nodos con edges condicionales. | ✅ Producción |
| 3 | **RouterAgent** | [`agents/router_agent.py`](webapp/intelligence/agents/router_agent.py) | Clasifica intención usando SemanticRouter (nodo inicial del grafo) | ✅ Producción |
| 4 | **ContextAgent** | [`agents/context_agent.py`](webapp/intelligence/agents/context_agent.py) | Resuelve contexto entre turnos (se salta si es primer turno) | ✅ Producción |
| 5 | **SearchAgent** | [`agents/search_agent.py`](webapp/intelligence/agents/search_agent.py) | Búsqueda RAG + FAISS + SQL pre-filtering | ✅ Producción |
| 6 | **FormatterAgent** | [`agents/formatter_agent.py`](webapp/intelligence/agents/formatter_agent.py) | Genera respuesta natural con DeepSeek | ✅ Producción |
| 7 | **ChatProcessor v2** | [`services/chat_processor.py`](webapp/intelligence/services/chat_processor.py) | DeepSeek como agente orquestador. Prompt engineering con skills, historial y RAG. | ✅ Producción |
| 8 | **RAG System** (SPEC-003) | [`services/rag.py`](webapp/intelligence/services/rag.py) | Embeddings all-MiniLM-L6-v2 (384d), FAISS HNSW, búsqueda semántica | ✅ Producción |
| 9 | **Memoria Episódica** | [`services/episodic_memory.py`](webapp/intelligence/services/episodic_memory.py) | Historial de mensajes por conversación | ✅ Producción |
| 10 | **Memoria de Hechos** | [`models.py`](webapp/intelligence/models.py) (Fact model) | Triples semánticos (sujeto-predicado-objeto + confianza) | ✅ Producción |
| 11 | **Contexto Activo** | [`services/context_manager.py`](webapp/intelligence/services/context_manager.py) | Parámetros de búsqueda persistentes entre turnos | ✅ Producción |
| 12 | **MetricsService** | [`services/metrics.py`](webapp/intelligence/services/metrics.py) | Logging estructurado, métricas de latencia, contexto manager | ✅ Producción |
| 13 | **SkillOrchestrator** | [`skills/orchestrator.py`](webapp/intelligence/skills/orchestrator.py) | Ejecución de skills con validación, cache, métricas y persistencia | ✅ Producción |
| 14 | **SkillRegistry** | [`skills/registry.py`](webapp/intelligence/skills/registry.py) | Registro central de skills con descubrimiento automático | ✅ Producción |
| 15 | **Evaluation Runner** (F5-001) | [`tests/evaluation/runner.py`](webapp/intelligence/tests/evaluation/runner.py) | Suite de evaluación con 52+ consultas del dataset | ✅ Operativo |
| 16 | **LLMService** | [`services/llm.py`](webapp/intelligence/services/llm.py) | Integración DeepSeek API con RAG context | ✅ Producción |

### Catálogo de Skills Implementadas

| Skill | Archivo | Descripción |
|---|---|---|
| `busqueda_propiedades` | [`skills/propiedades/skill.py`](webapp/intelligence/skills/propiedades/skill.py) | Búsqueda de propiedades con filtros semánticos |
| `acm_analisis` | [`skills/acm_analisis.py`](webapp/intelligence/skills/acm_analisis.py) | Análisis Comparativo de Mercado |
| `matching` | [`skills/matching.py`](webapp/intelligence/skills/matching.py) | Motor de matching oferta-demanda |
| `reporte_precios` | [`skills/reporte_precios.py`](webapp/intelligence/skills/reporte_precios.py) | Generación de reportes de precios por zona |
| `clasificar_intencion_whatsapp` | [`skills/clasificar_intencion_whatsapp.py`](webapp/intelligence/skills/clasificar_intencion_whatsapp.py) | Clasificación de mensajes WhatsApp |
| `resolver_contexto` | [`skills/resolver_contexto.py`](webapp/intelligence/skills/resolver_contexto.py) | Resolución de contexto entre turnos |
| `formatear_propiedades` | [`skills/formatear_propiedades.py`](webapp/intelligence/skills/formatear_propiedades.py) | Formateo de resultados de propiedades |
| `busqueda_exacta` | [`skills/busqueda_exacta.py`](webapp/intelligence/skills/busqueda_exacta.py) | Búsqueda exacta por ID o referencia |

### Gaps Remanentes

| # | Gap | Impacto | Dependencia |
|---|---|---|---|
| 1 | Sin function calling nativo de DeepSeek (tool_calls API) | El LLM no invoca tools directamente sino via prompt engineering | SDK DeepSeek |
| 2 | Sin WebSocket / streaming de respuestas | Experiencia de chat no es en tiempo real | SPEC-007 |
| 3 | Sin interfaz web chat interactiva (SPEC-007) | No hay frontend para usuarios finales | SPEC-007 |
| 4 | Sin pgvector (búsqueda vectorial en BD nativa) | FAISS in-memory no escala >10K docs | Infraestructura |
| 5 | Sin fine-tuning de embeddings para dominio inmobiliario | Precisión subóptima en queries peruanas | Dataset |

---

## 3. ARQUITECTURA IMPLEMENTADA

### Diagrama de Agentes (LangGraph StateGraph)

```
                    ┌──────────────────────────────────┐
                    │         PILOrchestrator          │
                    │      (LangGraph StateGraph)      │
                    └──────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
        ┌───────────────────┐   ┌───────────────────┐
        │   RouterAgent     │   │  ContextAgent     │
        │ (SemanticRouter)  │   │ (salta si ok)     │
        └────────┬──────────┘   └────────┬──────────┘
                 │                       │
                 └───────────┬───────────┘
                             ▼
                 ┌───────────────────┐
                 │   SearchAgent     │
                 │ (RAG + FAISS)     │
                 └────────┬──────────┘
                          │
                          ▼
                 ┌───────────────────┐
                 │  FormatterAgent   │
                 │ (DeepSeek resp.)  │
                 └───────────────────┘
```

### Flujo de Procesamiento (ChatProcessor v2)

```
Usuario → POST /api/v1/intelligence/chat/
       → ChatProcessor.process_message()
       → [LangGraph] PILOrchestrator.run()
           → RouterAgent.classify()       ← SemanticRouter (embeddings)
           → ContextAgent.resolve()       ← Memoria episódica + hechos
           → SearchAgent.search()         ← RAGService + FAISS
           → FormatterAgent.generate()    ← DeepSeek API
       → ChatResult(response, metadata)
```

---

## 4. SKILLS COMO TOOLS — Sistema Actual

El sistema actual usa **prompt engineering** donde DeepSeek decide qué skill ejecutar mediante un prompt de orquestación que lista las skills disponibles con sus schemas. DeepSeek responde con JSON estructurado indicando la skill y parámetros.

### Sistema Actual (Prompt-based)
```python
# ChatProcessor v2 — DeepSeek como orquestador
orchestration_prompt = build_orchestration_prompt(
    skills=SKILL_SYSTEM.get_all_skills(),
    history=conversation_history,
    user_message=message,
    facts=user_facts,
    rag_context=rag_results
)
# DeepSeek responde: {"skill": "busqueda_propiedades", "params": {...}}
decision = parse_orchestration_response(deepseek_response)
result = SKILL_SYSTEM.execute(decision.skill, decision.params, context)
```

### Próxima Evolución: Function Calling Nativo
```python
# Cuando DeepSeek SDK soporte tool_calls nativo
tools = [skill.to_openai_tool() for skill in SKILL_SYSTEM.get_all_skills()]
response = deepseek.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=tools  # ← function calling nativo
)
```

---

## 5. SISTEMA DE MEMORIAS (3 Capas)

| Capa | Tipo | Qué almacena | Modelo | Uso |
|---|---|---|---|---|
| 1 | **Memoria Episódica** | Historial de mensajes de la conversación actual | [`Conversation`](webapp/intelligence/models.py) (messages JSON) | Contexto inmediato para DeepSeek |
| 2 | **Memoria de Hechos** | Triples semánticos extraídos automáticamente | [`Fact`](webapp/intelligence/models.py) (sujeto-predicado-objeto + confianza) | Preferencias persistentes entre sesiones |
| 3 | **Contexto Activo** | Parámetros de búsqueda del turno anterior | [`Conversation`](webapp/intelligence/models.py) (metadata.contexto_activo_busqueda) | Mantener estado entre turnos |

### Integración en el Prompt
```
+--------------------------------------------------+
| System Prompt                                    |
+--------------------------------------------------+
| Instrucciones del sistema + skills disponibles    |
+--------------------------------------------------+
| Memoria Episódica (últimos N mensajes)           |
+--------------------------------------------------+
| Memoria de Hechos (preferencias del usuario)     |
+--------------------------------------------------+
| Contexto Activo (parámetros de búsqueda)         |
+--------------------------------------------------+
| Resultados RAG (propiedades recuperadas)         |
+--------------------------------------------------+
| Mensaje del usuario                              |
+--------------------------------------------------+
```

---

## 6. ORQUESTACIÓN CON LANGGRAPH — Estado Actual

### Implementación Actual ([`agents/orchestrator.py`](webapp/intelligence/agents/orchestrator.py))

```python
from langgraph.graph import StateGraph

class PILAgentState(TypedDict):
    message: str
    conversation_id: str
    user_id: Optional[str]
    skill_detectada: Optional[str]
    score_routing: float
    contexto_activo: Optional[Dict]
    resultados_busqueda: List[Dict]
    respuesta_generada: str
    nodos_ejecutados: List[str]
    trace_id: str
    latencia_total_ms: float
    error: Optional[str]

workflow = StateGraph(PILAgentState)

# 4 nodos del grafo
workflow.add_node("router", RouterAgent.run)
workflow.add_node("context", ContextAgent.run)
workflow.add_node("search", SearchAgent.run)
workflow.add_node("formatter", FormatterAgent.run)

# Edge condicional: saltar context si es primer turno
workflow.add_conditional_edges(
    "router",
    lambda state: "context" if state["contexto_activo"] else "search"
)
workflow.add_edge("context", "search")
workflow.add_edge("search", "formatter")

orchestrator = workflow.compile()
```

### Beneficios Actuales
- **Branching:** ContextAgent se salta si es primer turno
- **Checkpointing:** Estado se persiste en `PILAgentState`
- **Trazabilidad:** Cada nodo registra su ejecución en `nodos_ejecutados`
- **Métricas:** `latencia_total_ms` y métricas por nodo via MetricsService

### Próximas Mejoras
- **Loops:** Reintentar si resultados son insuficientes (< umbral)
- **Human-in-the-loop:** Pausar para aprobación manual
- **Parallel execution:** Ejecutar múltiples búsquedas en paralelo

---

## 7. ROADMAP DE EVOLUCIÓN

| Fase | Estado | Objetivo | Entregable |
|---|---|---|---|
| 1 | ✅ **COMPLETADO** | Function Calling (F1-001) | SemanticSkillRouter con embeddings E5-large |
| 2 | ✅ **COMPLETADO** | LangGraph Orchestration (F2-001) | PILOrchestrator con StateGraph y 4 agentes |
| 3 | ✅ **COMPLETADO** | Observabilidad | MetricsService, StructuredLogger, tracing |
| 4 | ✅ **COMPLETADO** | Multi-Agent | 4 agentes especializados (router, context, search, formatter) |
| 5 | ✅ **COMPLETADO** | Evaluación (F5-001) | EvaluationRunner con dataset de 52+ consultas |
| 6 | 🔄 **EN PROGRESO** | Chat Web Interactivo (SPEC-007) | Interfaz web tipo chat con panel lateral |
| 7 | 📋 **PLANEADO** | Function Calling Nativo | Migrar a tool_calls API de DeepSeek |
| 8 | 📋 **PLANEADO** | pgvector / Búsqueda Vectorial Nativa | Escalar más allá de 10K documentos |
| 9 | 📋 **PLANEADO** | Skills Avanzadas | Catálogo completo: reportes, notificaciones, scoring |

---

## 8. MÉTRICAS DE ÉXITO — Estado Actual vs Objetivo

| Métrica | Antes (v1) | Actual | Objetivo |
|---|---|---|---|
| Precisión detección de skill | ~70% (keyword) | ~85% (semántico) | >95% |
| Latencia promedio | ~1500ms | ~1200ms | <800ms |
| Falsos positivos en routing | ~20% | ~10% | <5% |
| Cobertura de consultas | ~60% | ~80% | >90% |
| Costo por consulta | $0.02 | $0.018 | $0.015 |
| Evaluación automática | No existía | ✅ 52 casos | >100 casos |

---

## 9. SIGUIENTES PASOS

### Inmediatos (SPEC-007)
- [ ] Implementar interfaz web chat interactiva (pendiente)
- [ ] Dashboard de monitoreo RAG en Django Admin
- [ ] Optimizar cache de embeddings para consultas frecuentes

### Corto plazo
1. **Function Calling Nativo**: Migrar de prompt engineering a `tool_calls` API de DeepSeek cuando esté disponible
2. **Streaming de respuestas**: Implementar SSE o WebSockets para experiencia en tiempo real
3. **Fine-tuning de embeddings**: Entrenar modelo con vocabulario inmobiliario peruano

### Mediano plazo
4. **pgvector**: Migrar búsqueda vectorial a PostgreSQL nativo para escalar >10K documentos
5. **Sistema de feedback**: Evaluación humana de calidad de respuestas
6. **Búsqueda multimodal**: Texto + imágenes + ubicación

---

## 10. PRINCIPIOS DE DESARROLLO

1. **Incremental, no reescritura** — Envolver código existente, no reemplazarlo
2. **Medir antes y después** — Cada cambio debe tener métricas (EvaluationRunner)
3. **Observabilidad primero** — No puedes mejorar lo que no puedes ver
4. **Skills atómicas** — Cada tool hace UNA cosa bien
5. **Estado persistente** — Todo se checkpointea en LangGraph
6. **Fallbacks graceful** — Si una tool falla, el agente puede continuar
7. **Cost-aware** — Monitorear tokens y optimizar cache
8. **🔴 DATOS COMPLETOS Y REALES SIEMPRE** — Nunca limitar, truncar o resumir resultados de búsqueda sin consultar al usuario. Cada vez que se devuelvan propiedades, debe ser la lista completa y real de la base de datos. La únicas excepción son:
   - El frontend puede paginar la visualización (pero el backend siempre retorna todo)
   - El usuario explícitamente pide "solo los primeros 5" o similar
   - Cualquier límite debe documentarse y justificarse en el código

---

## 11. REFERENCIAS

### SPECs Implementadas
| Documento | Descripción |
|---|---|
| [`SPEC-001_IMPLEMENTACION.md`](webapp/intelligence/SPEC-001_IMPLEMENTACION.md) | PIL v1.0 Base: modelos, API, roles, migraciones |
| [`SPEC-003_IMPLEMENTACION.md`](webapp/intelligence/SPEC-003_IMPLEMENTACION.md) | Sistema RAG: colecciones vectoriales, embeddings, DeepSeek |
| [`SPEC-007_PLAN_IMPLEMENTACION.md`](webapp/intelligence/SPEC-007_PLAN_IMPLEMENTACION.md) | Chat Web Interactivo (pendiente de implementación) |

### Archivos Clave del Sistema
- [`services/semantic_router.py`](webapp/intelligence/services/semantic_router.py) — Router semántico (F1-001)
- [`agents/orchestrator.py`](webapp/intelligence/agents/orchestrator.py) — Orquestador LangGraph (F2-001)
- [`services/chat_processor.py`](webapp/intelligence/services/chat_processor.py) — Procesador de chat v2
- [`services/rag.py`](webapp/intelligence/services/rag.py) — Sistema RAG
- [`services/llm.py`](webapp/intelligence/services/llm.py) — Integración DeepSeek
- [`services/metrics.py`](webapp/intelligence/services/metrics.py) — Observabilidad
- [`skills/orchestrator.py`](webapp/intelligence/skills/orchestrator.py) — Orquestador de skills
- [`tests/evaluation/runner.py`](webapp/intelligence/tests/evaluation/runner.py) — Evaluación automática

---

*Este documento es la fuente de verdad para la evolución de PIL hacia un sistema multi-agente completo.*
*Versión 2.0 — Actualizado con implementaciones F1-001, F2-001, F5-001 completadas.*
