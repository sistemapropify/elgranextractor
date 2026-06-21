# F4-001: Multi-Agent Architecture

> **Phase:** 4 — Multi-Agent
> **Priority:** 🟡 MEDIUM
> **Estimated Effort:** 8 days
> **Dependencies:** F2-001 (LangGraph), F3-001 (Observability)
> **Status:** Pending

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

- [x] **11.1** Separar `RouterAgent` del monolítico ChatProcessor
- [ ] **11.2** Implementar `SearchAgent` con RAGService + FAISS + SQL filtering
- [ ] **11.3** Implementar `ContextAgent` con memoria episódica + hechos + contexto
- [ ] **11.4** Implementar `FormatterAgent` con DeepSeek formateo
- [ ] **11.5** Implementar `MarketAgent` para análisis de mercado
- [ ] **11.6** Implementar `WhatsAppAgent` para extracción de requerimientos
- [ ] **11.7** Implementar comunicación agente-agente vía LangGraph
- [ ] **11.8** Migrar todo el tráfico de ChatProcessor a PIL Orchestrator

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

- [ ] **11.a** 6 agentes implementados con interfaces independientes
- [ ] **11.b** Cada agente puede ejecutarse y testearse aisladamente
- [ ] **11.c** Comunicación agente-agente via PILAgentState
- [ ] **11.d** Sin regression vs pipeline actual
- [ ] **11.e** Cobertura de tests >80% por agente
