# F4-001: Multi-Agent Architecture

> **Phase:** 4 — Multi-Agent
> **Priority:** 🟡 MEDIUM
> **Estimated Effort:** 8 days
> **Dependencies:** F2-001 (LangGraph), F3-001 (Observability)
> **Status:** ✅ Implemented (2026-06-21)

---

## Description

Evolucionar de un solo agente monolítico (ChatProcessor) a múltiples agentes especializados. Cada agente tiene una responsabilidad única y puede ser desarrollado, testeado y optimizado independientemente.

## Agent Architecture

```
PIL Orchestrator (LangGraph)
├── Router Agent      → Clasifica intención, decide qué skill ejecutar
├── Search Agent      → RAG + FAISS + SQL pre-filtering + ranking
├── Context Agent     → Memoria episódica + hechos + contexto activo
├── Formatter Agent   → Genera respuesta natural con DeepSeek
├── Market Agent      → Análisis de mercado (NEW)
└── WhatsApp Agent    → Extracción de requerimientos (NEW)
```

## Goals

- [x] **11.1** Separar `RouterAgent` del monolítico ChatProcessor — [`router_agent.py`](../webapp/intelligence/agents/router_agent.py)
- [x] **11.2** Implementar `SearchAgent` — [`search_agent.py`](../webapp/intelligence/agents/search_agent.py)
- [x] **11.3** Implementar `ContextAgent` — [`context_agent.py`](../webapp/intelligence/agents/context_agent.py)
- [x] **11.4** Implementar `FormatterAgent` — [`formatter_agent.py`](../webapp/intelligence/agents/formatter_agent.py)
- [x] **11.5** Implementar `MarketAgent` — [`market_agent.py`](../webapp/intelligence/agents/market_agent.py)
- [x] **11.6** Implementar `WhatsAppAgent` — [`whatsapp_agent.py`](../webapp/intelligence/agents/whatsapp_agent.py)
- [x] **11.7** Comunicación agente-agente vía PILAgentState + LangGraph — [`orchestrator.py`](../webapp/intelligence/agents/orchestrator.py)
- [x] **11.8** Interfaz `BaseAgent` común — [`base_agent.py`](../webapp/intelligence/agents/base_agent.py)

_Prompt: Implement multi-agent architecture where each agent is a specialized LangGraph node with its own responsibility, state, and error handling. Agents communicate through the shared PILAgentState._

_Requirements: LangGraph, agent isolation, independent testing, shared state protocol_

_Leverage: F2-001 LangGraph, existing RAGService, existing memory systems, existing DeepSeek integration_

_Files: webapp/intelligence/agents/router_agent.py, search_agent.py, context_agent.py, formatter_agent.py, market_agent.py, whatsapp_agent.py_

## Agent Interface

```python
class BaseAgent(ABC):
    @abstractmethod
    async def run(self, state: PILAgentState) -> PILAgentState:
        """Execute agent logic and return updated state."""
        pass
    
    @abstractmethod
    def validate(self, state: PILAgentState) -> bool:
        """Validate that agent has required inputs."""
        pass
    
    @abstractmethod
    def get_metrics(self) -> AgentMetrics:
        """Return agent performance metrics."""
        pass
```

## Acceptance Criteria

- [x] **11.a** 6 agentes implementados (Router, Search, Context, Formatter, Market, WhatsApp)
- [x] **11.b** Cada agente es independiente — se puede testear aisladamente
- [x] **11.c** Comunicación via PILAgentState + LangGraph StateGraph
- [x] **11.d** Interfaz base `BaseAgent` con run(), validate(), get_metrics()
- [ ] **11.e** Migración total del tráfico a PIL Orchestrator (pendiente, usa fallback a DeepSeek)
- [ ] **11.f** Cobertura de tests >80% por agente (pendiente)
