# PIL (PropiFai Intelligence Layer) — Visión Arquitectónica

> **Documento fuente de verdad para la evolución de PIL hacia un sistema multi-agente completo.**
> **Versión:** 1.0 — Junio 2026
> **Propósito:** Contexto fundamental para MCP, desarrollo y referencia arquitectónica

---

## 1. VISIÓN

PIL es un sistema multi-agente especializado en el dominio inmobiliario que evoluciona desde un sistema de skills clásico hacia una arquitectura agentica completa. La potencia del sistema no radica en el LLM (DeepSeek), sino en las skills/tools que puede invocar y en cómo las orquesta.

**OBJETIVO FINAL:** PIL será un sistema completo capaz de:
- Entender requerimientos complejos en lenguaje natural
- Razonar sobre qué acciones ejecutar
- Coordinar múltiples agentes especializados
- Aprender de cada interacción
- Ejecutar tareas complejas de extremo a extremo

---

## 2. ESTADO ACTUAL (Base Sólida — 60%)

### Componentes Existentes

| # | Componente | Función | Equivalente Agentico |
|---|-----------|---------|---------------------|
| 1 | RAG E5-large + FAISS HNSW | Búsqueda semántica de propiedades | Retrieval tool |
| 2 | Memoria episódica | Historial de conversación | Short-term memory |
| 3 | Memoria de hechos | Triples semánticos (sujeto-predicado-objeto) | Long-term memory |
| 4 | Context manager | Parámetros de búsqueda entre turnos | Working memory / State |
| 5 | DeepSeek (3 roles) | RAG, formateo, extracción de parámetros | LLM core |
| 6 | Skills con schemas | busqueda_propiedades, resolver_contexto | Proto-tools |
| 7 | Cache LRU | Embeddings y ejecución de skills | Semantic cache |
| 8 | Azure SQL + Celery + Django | Stack productivo | Execution environment |

### Gaps Críticos

| # | Gap | Impacto |
|---|-----|---------|
| 1 | Sin function calling estructurado | El LLM no decide qué tools usar |
| 2 | Skill matching por keywords (no semántico) | Falsos negativos en detección de intención |
| 3 | Pipeline secuencial rígido | No puede hacer branching ni loops |
| 4 | Sin observabilidad | No se puede depurar decisiones del agente |
| 5 | Sin evaluación sistemática | No se mide si el agente mejora |
| 6 | Un solo agente monolítico | No hay especialización |

---

## 3. ARQUITECTURA OBJETIVO

### Principios de Diseño

1. **Skills como tools reales** — Cada skill es una función que el LLM puede invocar via function calling
2. **Orquestación con grafos de estado** — LangGraph reemplaza el pipeline secuencial
3. **Multi-agente especializado** — Agentes diferentes para tareas diferentes
4. **Memoria persistente** — Estado se checkpointea y persiste entre sesiones
5. **Observabilidad total** — Cada decisión queda trazada
6. **Evaluación continua** — Métricas automáticas de calidad

### Arquitectura de Agentes

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

---

## 4. SKILLS COMO TOOLS — Function Calling

**Evolución:** De skills clásicas a function calling

### ANTES (sistema actual — routing manual)
```python
if "buscar" in message or "propiedad" in message:
    skill = "busqueda_propiedades"
    params = LLMService.extract_skill_params(message, schema)
    result = SKILL_SYSTEM.execute_skill(skill, params)
```

### DESPUÉS (function calling — DeepSeek decide)
```python
tools = [{
    "type": "function",
    "function": {
        "name": "buscar_propiedades",
        "description": "Busca propiedades en PROPIFAI según criterios",
        "parameters": {
            "type": "object",
            "properties": {
                "distrito": {"type": "string"},
                "tipo_propiedad": {"type": "string"},
                "precio_max": {"type": "number"},
                "habitaciones": {"type": "integer"}
            }
        }
    }
}]

response = deepseek.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": message}],
    tools=tools
)

if response.choices[0].message.tool_calls:
    tool_call = response.choices[0].message.tool_calls[0]
    result = execute_tool(tool_call.function.name, tool_call.function.arguments)
```

### Catálogo de Skills/Tools (Roadmap)

| # | Skill | Estado | Prioridad |
|---|-------|--------|-----------|
| 1 | buscar_propiedades | Existe | Migrar a function calling |
| 2 | resolver_contexto | Existe | Optimizar (saltar si turno 1) |
| 3 | analizar_mercado | Planeada | Alta |
| 4 | extraer_requerimientos_whatsapp | Planeada | Alta |
| 5 | generar_reporte_zona | Planeada | Media |
| 6 | calcular_scoring_propiedad | Planeada | Media |
| 7 | enviar_notificacion_agente | Planeada | Baja |

---

## 5. SISTEMA DE MEMORIAS (3 Capas)

| Capa | Tipo | Qué almacena | Dónde | Uso |
|------|------|-------------|-------|-----|
| 1 | Memoria Episódica | Historial de mensajes de la conversación actual | ConversationMessage model | Contexto inmediato para DeepSeek |
| 2 | Memoria de Hechos | Triples semánticos extraídos automáticamente | FactMemory model (sujeto-predicado-objeto + confianza) | Preferencias persistentes entre sesiones |
| 3 | Contexto Activo | Parámetros de búsqueda del turno anterior | conversation.metadata['contexto_activo_busqueda'] | Mantener estado entre turnos |

### Integración en el Prompt
```
+--------------------------------------------------+
| System Prompt                                    |
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

## 6. ORQUESTACIÓN CON LANGGRAPH

### Reemplazo del Pipeline Secuencial

```python
from langgraph.graph import StateGraph
from typing import TypedDict, Optional

class PILAgentState(TypedDict):
    message: str
    conversation_id: str
    contexto_activo: dict
    hechos_usuario: list
    skill_detectada: Optional[str]
    params_extraidos: dict
    resultados_busqueda: list
    respuesta: str

workflow = StateGraph(PILAgentState)
workflow.add_node("clasificar_intencion", router_agent)
workflow.add_node("resolver_contexto", context_agent)
workflow.add_node("buscar_propiedades", search_agent)
workflow.add_node("generar_respuesta", formatter_agent)

workflow.add_conditional_edges(
    "clasificar_intencion",
    lambda state: (
        "resolver_contexto" if state["contexto_activo"] 
        else "buscar_propiedades"
    )
)
workflow.add_edge("resolver_contexto", "buscar_propiedades")
workflow.add_edge("buscar_propiedades", "generar_respuesta")

agent = workflow.compile()
```

### Beneficios
- **Branching:** Saltar resolver_contexto si es turno 1
- **Checkpointing:** Estado se persiste
- **Loops:** Agente puede reintentar si resultados son insuficientes
- **Human-in-the-loop:** Pausar para aprobación manual

---

## 7. ROADMAP DE EVOLUCIÓN

| Fase | Semanas | Objetivo | Entregable |
|------|---------|----------|------------|
| 1 | 1-2 | Function Calling | DeepSeek decide qué tool usar sin routing manual |
| 2 | 3-4 | LangGraph Orchestration | Orquestación flexible con branching |
| 3 | 5 | Observabilidad | Capacidad de depurar decisiones del agente |
| 4 | 6-8 | Multi-Agent | Sistema multi-agente especializado |
| 5 | 9-10 | Evaluación y Optimización | Suite de tests que corre antes de cada deploy |
| 6 | Mes 3+ | Skills Avanzadas | Catálogo completo de skills |

---

## 8. MÉTRICAS DE ÉXITO

| Métrica | Actual | Objetivo |
|---------|--------|----------|
| Precisión detección de skill | ~70% | >95% |
| Latencia promedio | ~1500ms | <800ms |
| Falsos positivos en routing | ~20% | <5% |
| Cobertura de consultas | ~60% | >90% |
| Costo por consulta | $0.02 | $0.015 |
| Satisfacción usuario | No medido | >4.5/5 |

---

## 9. PRIMER PASO INMEDIATO

**PROYECTO:** Semantic Skill Router (10 horas)

**OBJETIVO:** Reemplazar SkillRegistry (keyword matching) por clasificación semántica con embeddings.

**ARCHIVOS:**
- `webapp/intelligence/services/semantic_router.py` (nuevo)
- `webapp/intelligence/services/chat_processor.py` (integrar router)

**CRITERIOS DE ÉXITO:**
- "donde construir un colegio" detecta busqueda_propiedades con score >0.7
- "busco departamento en Cayma" score >0.9
- "hola" score <0.3 (fallback a RAG puro)

**IMPACTO:** Resuelve problema #1 (matching de tokens) y #8 (umbral bajo)

---

## 10. PRINCIPIOS DE DESARROLLO

1. **Incremental, no reescritura** — Envolver código existente, no reemplazarlo
2. **Medir antes y después** — Cada cambio debe tener métricas
3. **Observabilidad primero** — No puedes mejorar lo que no puedes ver
4. **Skills atómicas** — Cada tool hace UNA cosa bien
5. **Estado persistente** — Todo se checkpointea
6. **Fallbacks graceful** — Si una tool falla, el agente puede continuar
7. **Cost-aware** — Monitorear tokens y optimizar cache

---

*Este documento es la fuente de verdad para la evolución de PIL hacia un sistema multi-agente completo.*
