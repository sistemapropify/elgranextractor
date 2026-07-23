"""
PIL Orchestrator — Orquestador multi-agente con LangGraph StateGraph.

F2-001: Reemplaza el pipeline secuencial de ChatProcessor.process_message()
por un grafo dirigido con 4 nodos y edges condicionales.

Estructura del grafo:
    router_agent → (context_agent)? → search_agent → formatter_agent

Arquitectura:
    - router_agent: Clasifica intención (SemanticRouter)
    - context_agent: Resuelve contexto (se salta si es primer turno)
    - search_agent: Búsqueda RAG + FAISS + SQL pre-filtering
    - formatter_agent: Genera respuesta con DeepSeek
"""

from __future__ import annotations

import json
import logging
import time
import hashlib
import traceback
from typing import Any, Dict, List, Optional, TypedDict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# PILAgentState — TypedDict del estado del grafo (F2-001 6.2)
# ═══════════════════════════════════════════════════════════════════════════════


class PILAgentState(TypedDict):
    """Estado del agente PIL que fluye a través del grafo LangGraph.

    Cada nodo del grafo lee y escribe en este estado.
    Los campos marcados con ? son opcionales o se llenan durante la ejecución.
    """
    # ── Input ──
    message: str
    conversation_id: str
    user_id: Optional[str]

    # ── Router ──
    skill_detectada: Optional[str]
    score_routing: float
    threshold: float
    router_latency_ms: float
    matched_template: str
    fallback_used: bool

    # ── Context ──
    contexto_activo: Optional[Dict[str, Any]]
    contexto_resuelto: bool
    hechos_usuario: List[Dict[str, Any]]
    params_extraidos: Dict[str, Any]
    search_plan: Optional[Dict[str, Any]]
    search_plan_hash: str
    fallback_plan_reused: bool
    search_failed: bool

    # ── User Context (SPEC v2.0 - Multi-Rol) ──
    user_context: Optional[Dict[str, Any]]

    # ── Search ──
    resultados_busqueda: List[Dict[str, Any]]
    filtros_aplicados: Dict[str, Any]
    total_resultados: int

    # ── Response ──
    respuesta_generada: str
    documentos_referencia: List[Dict[str, Any]]
    respuesta_raw: Optional[str]

    # ── Tracing ──
    nodos_ejecutados: List[str]
    trace_id: str
    latencia_total_ms: float
    error: Optional[str]


def create_initial_state(
    message: str,
    conversation_id: str,
    user_id: Optional[str] = None,
    contexto_activo: Optional[Dict[str, Any]] = None,
    user_context: Optional[Dict[str, Any]] = None,
    search_plan: Optional[Dict[str, Any]] = None,
) -> PILAgentState:
    """Crea un estado inicial para el grafo.

    Args:
        message: Mensaje del usuario
        conversation_id: ID de la conversación
        user_id: ID del usuario (opcional)
        contexto_activo: Contexto activo de la conversación (opcional)
        user_context: Contexto del usuario para adaptación multi-rol (SPEC v2.0)
    """
    return PILAgentState(
        # Input
        message=message,
        conversation_id=conversation_id,
        user_id=user_id,
        # Router
        skill_detectada=None,
        score_routing=0.0,
        threshold=0.45,
        router_latency_ms=0.0,
        matched_template='',
        fallback_used=False,
        # Context
        contexto_activo=contexto_activo or {},
        contexto_resuelto=False,
        hechos_usuario=[],
        params_extraidos={},
        search_plan=search_plan,
        search_plan_hash='',
        fallback_plan_reused=False,
        search_failed=False,
        # User Context (SPEC v2.0)
        user_context=user_context,
        # Search
        resultados_busqueda=[],
        filtros_aplicados={},
        total_resultados=0,
        # Response
        respuesta_generada='',
        documentos_referencia=[],
        respuesta_raw=None,
        # Tracing
        nodos_ejecutados=[],
        trace_id=hashlib.md5(
            f"{conversation_id}:{message}:{time.time()}".encode()
        ).hexdigest()[:12],
        latencia_total_ms=0.0,
        error=None,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Node Functions
# ═══════════════════════════════════════════════════════════════════════════════
# Cada función recibe el estado actual y retorna las actualizaciones.
# ═══════════════════════════════════════════════════════════════════════════════


def router_node(state: PILAgentState) -> Dict[str, Any]:
    """Nodo: Clasificar intención del usuario."""
    from .router_agent import RouterAgent
    result = RouterAgent.run(dict(state))

    # Tracking
    result['nodos_ejecutados'] = state.get('nodos_ejecutados', []) + ['router']

    return result


def context_node(state: PILAgentState) -> Dict[str, Any]:
    """Nodo: Resolver contexto conversacional (opcional)."""
    from .context_agent import ContextAgent
    result = ContextAgent.run(dict(state))

    # Tracking
    result['nodos_ejecutados'] = state.get('nodos_ejecutados', []) + ['context']

    return result


def search_node(state: PILAgentState) -> Dict[str, Any]:
    """Nodo: Búsqueda RAG con FAISS + SQL pre-filtering."""
    from .search_agent import SearchAgent
    result = SearchAgent.run(dict(state))

    # Tracking
    result['nodos_ejecutados'] = state.get('nodos_ejecutados', []) + ['search']

    return result


def formatter_node(state: PILAgentState) -> Dict[str, Any]:
    """Nodo: Generar respuesta formateada con DeepSeek."""
    from .formatter_agent import FormatterAgent
    result = FormatterAgent.run(dict(state))

    # Tracking
    result['nodos_ejecutados'] = state.get('nodos_ejecutados', []) + ['formatter']
    result['latencia_total_ms'] = time.time() * 1000 - float(
        state.get('_start_time', time.time() * 1000)
    )

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Conditional Edge Functions
# ═══════════════════════════════════════════════════════════════════════════════


def should_resolve_context(state: PILAgentState) -> str:
    """
    Decide si ejecutar context_agent o saltar directamente a search.

    F2-001 (6.7): Conditional edge.
    - Si hay contexto_activo del turno anterior → ejecutar context_agent
    - Si es primer turno (contexto_activo vacío) → saltar a search

    Returns:
        "context_resolver" | "search"  (nombre del siguiente nodo)
    """
    contexto = state.get('contexto_activo', {})
    tiene_contexto = bool(contexto) and len(contexto) > 0

    if tiene_contexto:
        logger.debug(
            f"[F2-001] Conditional edge: contexto activo detectado → "
            f"ejecutar context_agent"
        )
        return "context_resolver"
    else:
        logger.debug(
            f"[F2-001] Conditional edge: sin contexto activo → "
            f"saltar a search"
        )
        return "search"


# ═══════════════════════════════════════════════════════════════════════════════
# PILOrchestrator — LangGraph StateGraph Builder
# ═══════════════════════════════════════════════════════════════════════════════


class PILOrchestrator:
    """
    Orquestador multi-agente usando LangGraph StateGraph.

    Uso:
        orchestrator = PILOrchestrator()
        result = orchestrator.run(
            message="busco departamento en Cayma",
            conversation_id="...",
            user_id="...",
            contexto_activo={"distrito": "Cayma"}
        )
        print(result['respuesta_generada'])
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.graph = None
        self._build_graph()

    def _build_graph(self):
        """
        Construye el StateGraph de LangGraph.

        F2-001: Grafo con 4 nodos y 1 edge condicional.
        """
        try:
            from langgraph.graph import StateGraph, END

            graph = StateGraph(PILAgentState)

            # ── Nodos ──
            graph.add_node("router", router_node)
            graph.add_node("context_resolver", context_node)
            graph.add_node("search", search_node)
            graph.add_node("formatter", formatter_node)

            # ── Edges ──
            # Router → (context_resolver | search)
            graph.add_conditional_edges(
                "router",
                should_resolve_context,
                {
                    "context_resolver": "context_resolver",
                    "search": "search",
                }
            )

            # context_resolver → search
            graph.add_edge("context_resolver", "search")

            # search → formatter
            graph.add_edge("search", "formatter")

            # formatter → END
            graph.add_edge("formatter", END)

            # Entry point
            graph.set_entry_point("router")

            # Compilar
            self.graph = graph.compile()

            logger.info(
                "[F2-001] PILOrchestrator: StateGraph compilado con "
                "4 nodos (router, context_resolver, search, formatter)"
            )

        except ImportError as e:
            logger.warning(
                f"[F2-001] LangGraph no disponible: {e}. "
                f"Usando pipeline secuencial como fallback."
            )
            self.graph = None
        except Exception as e:
            logger.error(f"[F2-001] Error construyendo StateGraph: {e}")
            self.graph = None

    def run(
        self,
        message: str,
        conversation_id: str,
        user_id: Optional[str] = None,
        contexto_activo: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        search_plan: Optional[Dict[str, Any]] = None,
    ) -> PILAgentState:
        """
        Ejecuta el grafo completo.

        Args:
            message: Mensaje del usuario
            conversation_id: ID de la conversación
            user_id: ID del usuario (opcional)
            contexto_activo: Contexto del turno anterior (opcional)
            user_context: Contexto del usuario para adaptación multi-rol (SPEC v2.0)

        Returns:
            PILAgentState con todos los resultados
        """
        start = time.time()

        # Crear estado inicial
        state = create_initial_state(
            message=message,
            conversation_id=conversation_id,
            user_id=user_id,
            contexto_activo=contexto_activo,
            user_context=user_context,
            search_plan=search_plan,
        )
        if search_plan:
            from ..search.contracts import SearchPlan
            state['search_plan_hash'] = SearchPlan.from_dict(search_plan).fingerprint()
        state['_start_time'] = start * 1000

        logger.info(
            f"[F2-001] PILOrchestrator.run: "
            f"trace_id={state['trace_id']} | "
            f"message='{message[:80]}...' | "
            f"conv={conversation_id}"
        )

        try:
            if self.graph is not None:
                # ── Ejecutar LangGraph ──
                result = self.graph.invoke(state)

                logger.info(
                    f"[F2-001] PILOrchestrator: LangGraph completado | "
                    f"trace_id={result.get('trace_id', '')} | "
                    f"nodos={result.get('nodos_ejecutados', [])} | "
                    f"skill={result.get('skill_detectada')} | "
                    f"resultados={result.get('total_resultados', 0)}"
                )

                return result

            else:
                # ── Fallback: pipeline secuencial ──
                logger.info(
                    f"[F2-001] PILOrchestrator: usando fallback secuencial"
                )

                state = router_node(state)
                state = context_node(state) if should_resolve_context(state) == 'context_resolver' else state
                state = search_node(state)
                state = formatter_node(state)

                return state

        except Exception as e:
            logger.error(
                f"[F2-001] PILOrchestrator error: {e}\n"
                f"{traceback.format_exc()}"
            )
            state['error'] = str(e)
            state['respuesta_generada'] = (
                "Lo siento, ocurrió un error al procesar tu mensaje. "
                "Por favor intenta de nuevo."
            )
            return state


# ═══════════════════════════════════════════════════════════════════════════════
# NUEVA ARQUITECTURA: Agentes Independientes (SPEC refactor_plataforma_agentes)
# ═══════════════════════════════════════════════════════════════════════════════
# Fase 5 + Fase 6: Ejecución paralela con namespaces
# ═══════════════════════════════════════════════════════════════════════════════


class AgentOrchestratorState(TypedDict):
    """
    Estado del nuevo grafo de agentes (Fase 5 + Fase 6).

    Cada agente escribe EXCLUSIVAMENTE en results[agent_name],
    nunca en una clave compartida sin prefijo — esto evita conflictos
    cuando dos agentes corren en paralelo.
    """
    # ── Input ──
    message: str
    conversation_id: str
    user_id: Optional[str]
    user_level: int
    user_context: Optional[Dict[str, Any]]

    # ── Supervisor ──
    routing_plan: Dict[str, Any]       # resultado de Supervisor.route()
    agents_activated: List[str]        # nombres de agentes a ejecutar

    # ── Namespaces por agente — nunca se cruzan ──
    results: Dict[str, Any]            # results[agent_name] = AgentResult

    # ── Agregación ──
    aggregated_answer: Optional[Dict[str, Any]]
    critique_passed: bool
    critique_retries: int

    # ── Tracing ──
    trace_id: str
    latencia_total_ms: float
    error: Optional[str]


def create_agent_initial_state(
    message: str,
    conversation_id: str,
    user_id: Optional[str] = None,
    user_context: Optional[Dict[str, Any]] = None,
) -> AgentOrchestratorState:
    """Crea un estado inicial para el grafo de agentes."""
    import hashlib
    return AgentOrchestratorState(
        message=message,
        conversation_id=conversation_id,
        user_id=user_id,
        user_level=(user_context or {}).get('level', 1),
        user_context=user_context,
        routing_plan={},
        agents_activated=[],
        results={},
        aggregated_answer=None,
        critique_passed=True,
        critique_retries=0,
        trace_id=hashlib.md5(
            f"agent:{conversation_id}:{message}:{time.time()}".encode()
        ).hexdigest()[:12],
        latencia_total_ms=0.0,
        error=None,
    )


# ── Node functions ──────────────────────────────────────────────────────────


def supervisor_node(state: AgentOrchestratorState) -> Dict[str, Any]:
    """
    Nodo: Supervisor decide qué agente(s) activar.

    Reutiliza Supervisor.route() que internamente usa SemanticSkillRouter
    con templates de agentes.
    """
    from .supervisor import Supervisor

    supervisor = Supervisor()
    plan = supervisor.route(
        message=state.get('message', ''),
        user_level=state.get('user_level', 1),
        user_context=state.get('user_context'),
    )

    agents = [a['name'] for a in plan.get('agents', [])]

    logger.info(
        f"[AgentGraph] Supervisor: {len(agents)} agente(s) activados: "
        f"{agents}, modo={plan.get('execution_mode', 'single')}"
    )

    return {
        'routing_plan': plan,
        'agents_activated': agents,
        'nodos_ejecutados': state.get('nodos_ejecutados', []) + ['supervisor'],
    }


def _build_agent_node(agent_name: str):
    """
    Factory de nodos de agente para el grafo.

    Cada nodo de agente corre independientemente (pueden ejecutarse en paralelo).
    Escribe SOLO en state['results'][agent_name].
    """
    def agent_node(state: AgentOrchestratorState) -> Dict[str, Any]:
        from .registry import AgentRegistry

        registry = AgentRegistry()
        agent = registry.get_by_name(agent_name)

        if not agent:
            logger.warning(f"[AgentGraph] Agente '{agent_name}' no encontrado")
            return {
                'results': {
                    agent_name: {
                        'agent_name': agent_name,
                        'success': False,
                        'error_message': f"Agente '{agent_name}' no registrado",
                        'steps': [],
                        'iterations_used': 0,
                        'confidence': 0.0,
                    }
                }
            }

        start = time.time()
        logger.info(f"[AgentGraph] Ejecutando agente: '{agent_name}'")

        try:
            result = agent.run(
                message=state.get('message', ''),
                context={
                    'user_id': state.get('user_id'),
                    'user_level': state.get('user_level', 1),
                    'user_context': state.get('user_context'),
                    'conversation_id': state.get('conversation_id'),
                },
            )
            duration_ms = (time.time() - start) * 1000
            logger.info(
                f"[AgentGraph] Agente '{agent_name}' completado: "
                f"success={result.success}, "
                f"iterations={result.iterations_used}, "
                f"confidence={result.confidence:.2f}, "
                f"duration={duration_ms:.0f}ms"
            )
            return {
                'results': {agent_name: result.to_log() if hasattr(result, 'to_log') else result},
                'nodos_ejecutados': state.get('nodos_ejecutados', []) + [agent_name],
            }
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            logger.error(f"[AgentGraph] Error en agente '{agent_name}': {e}")
            return {
                'results': {
                    agent_name: {
                        'agent_name': agent_name,
                        'success': False,
                        'error_message': str(e),
                        'steps': [],
                        'iterations_used': 0,
                        'confidence': 0.0,
                    }
                },
                'nodos_ejecutados': state.get('nodos_ejecutados', []) + [f'{agent_name}:error'],
            }

    return agent_node


def aggregator_node(state: AgentOrchestratorState) -> Dict[str, Any]:
    """
    Nodo: Agrega resultados de todos los agentes activados.

    Fan-in: recibe resultados de N agentes y los consolida.
    Si algún agente falló, se registra pero no bloquea a los demás.
    """
    agents = state.get('agents_activated', [])
    results = state.get('results', {})
    successful = []
    failed = []

    for agent_name in agents:
        result = results.get(agent_name, {})
        if result.get('success', False):
            successful.append({
                'name': agent_name,
                'final_answer': result.get('final_answer'),
                'confidence': result.get('confidence', 0.0),
            })
        else:
            failed.append({
                'name': agent_name,
                'error': result.get('error_message', 'unknown error'),
            })

    logger.info(
        f"[AgentGraph] Aggregator: {len(successful)} exitosos, "
        f"{len(failed)} fallidos de {len(agents)} agentes"
    )

    return {
        'aggregated_answer': {
            'successful': successful,
            'failed': failed,
            'total_agents': len(agents),
            'successful_count': len(successful),
            'failed_count': len(failed),
        },
        'nodos_ejecutados': state.get('nodos_ejecutados', []) + ['aggregator'],
    }


def self_critique_node(state: AgentOrchestratorState) -> Dict[str, Any]:
    """
    Nodo: Autocrítica antes de responder.

    Evalúa si el resultado agregado es suficiente.
    Si no es suficiente y hay reintentos disponibles, marca para reintentar.
    """
    aggregated = state.get('aggregated_answer', {})
    successful = aggregated.get('successful', [])

    # Si al menos un agente tuvo éxito, la respuesta es suficiente
    is_sufficient = len(successful) > 0
    retries = state.get('critique_retries', 0)

    if not is_sufficient and retries < 1:
        logger.info(
            "[AgentGraph] Autocrítica: respuesta insuficiente, "
            "reintentando con agente fallback RAG"
        )
        return {
            'critique_passed': False,
            'critique_retries': retries + 1,
            'agents_activated': ['agente_fallback_rag'],
            'nodos_ejecutados': state.get('nodos_ejecutados', []) + ['self_critique:retry'],
        }

    logger.info(
        f"[AgentGraph] Autocrítica: respuesta {'suficiente' if is_sufficient else 'insuficiente, sin reintentos'}"
    )
    return {
        'critique_passed': is_sufficient,
        'nodos_ejecutados': state.get('nodos_ejecutados', []) + ['self_critique'],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# AgentGraphBuilder — Construye el grafo LangGraph con fan-out/fan-in
# ═══════════════════════════════════════════════════════════════════════════════


class AgentGraphBuilder:
    """
    Construye el grafo LangGraph con fan-out/fan-in de agentes.

    Estructura:
        supervisor
          │  (fan-out condicional: decide qué agente(s) activar)
          ├──▶ agente_propiedades
          ├──▶ agente_mercado
          ├──▶ agente_requerimientos
          │  (fan-in: todos convergen en aggregator)
          ▼
        aggregator
          │
          ▼
        self_critique
          │
          ▼
        (END)

    El supervisor decide el fan-out basado en la consulta.
    Si solo se activa 1 agente, el grafo corre en modo single.
    Si se activan 2+, el grafo corre con ejecución paralela.
    """

    # Agentes disponibles en el grafo
    _AGENT_NODES = [
        'agente_propiedades',
        'agente_mercado',
        'agente_requerimientos',
    ]

    def __init__(self):
        self.graph = None
        self._build()

    def _build(self) -> None:
        """Construye el grafo LangGraph."""
        try:
            from langgraph.graph import END, StateGraph

            graph = StateGraph(AgentOrchestratorState)

            # Nodos del grafo
            graph.add_node("supervisor", supervisor_node)
            for agent_name in self._AGENT_NODES:
                graph.add_node(agent_name, _build_agent_node(agent_name))
            graph.add_node("aggregator", aggregator_node)
            graph.add_node("self_critique", self_critique_node)

            # Fan-out: supervisor → agente(s) según routing_plan
            graph.add_conditional_edges(
                "supervisor",
                self._route_to_agents,
                {name: name for name in self._AGENT_NODES},
            )

            # Fan-in: todos los agentes → aggregator
            for agent_name in self._AGENT_NODES:
                graph.add_edge(agent_name, "aggregator")

            # aggregator → self_critique
            graph.add_edge("aggregator", "self_critique")

            # self_critique → END (con posible reintento manejado por el nodo mismo)
            graph.add_edge("self_critique", END)

            # Entry point
            graph.set_entry_point("supervisor")

            self.graph = graph.compile()

            logger.info(
                f"[AgentGraph] Grafo compilado con "
                f"{1 + len(self._AGENT_NODES) + 2} nodos "
                f"(supervisor, {len(self._AGENT_NODES)} agentes, "
                f"aggregator, self_critique)"
            )

        except ImportError as e:
            logger.warning(
                f"[AgentGraph] LangGraph no disponible: {e}. "
                f"Usando pipeline legacy como fallback."
            )
            self.graph = None
        except Exception as e:
            logger.error(f"[AgentGraph] Error construyendo grafo: {e}")
            self.graph = None

    def _route_to_agents(self, state: AgentOrchestratorState) -> str:
        """
        Decide a qué nodo(s) de agente enviar según el plan del Supervisor.

        Retorna el nombre del primer agente (LangGraph no soporta fan-out
        dinámico nativo; la ejecución paralela real se maneja con
        concurrent.futures en run()).
        """
        agents = state.get('agents_activated', [])
        if agents:
            # Retornar el primer agente activado como destino del edge condicional.
            # Los demás agentes se ejecutan en paralelo via concurrent.futures en run().
            return agents[0] if agents[0] in self._AGENT_NODES else self._AGENT_NODES[0]

        return self._AGENT_NODES[0]  # fallback al primer agente disponible

    def run(
        self,
        message: str,
        conversation_id: str,
        user_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
        search_plan: Optional[Dict[str, Any]] = None,
    ) -> AgentOrchestratorState:
        """
        Ejecuta el grafo de agentes completo.

        Para consultas multi-agente, usa concurrent.futures para
        ejecución paralela real.

        Args:
            message: Mensaje del usuario
            conversation_id: ID de la conversación
            user_id: ID del usuario
            user_context: Contexto del usuario

        Returns:
            AgentOrchestratorState con resultados de todos los agentes
        """
        start = time.time()

        # Paso 1: Supervisor determina qué agente(s) activar
        from .supervisor import Supervisor
        supervisor = Supervisor()
        plan = supervisor.route(
            message=message,
            user_level=(user_context or {}).get('level', 1),
            user_context=user_context,
        )

        agents = [a['name'] for a in plan.get('agents', []) if a['name'] in self._AGENT_NODES]
        if not agents:
            agents = ['agente_propiedades']  # fallback

        logger.info(
            f"[AgentGraph] Plan: {len(agents)} agente(s), "
            f"modo={plan.get('execution_mode', 'single')}"
        )

        # Crear estado inicial
        state = create_agent_initial_state(
            message=message,
            conversation_id=conversation_id,
            user_id=user_id,
            user_context=user_context,
        )
        state['routing_plan'] = plan
        state['agents_activated'] = agents

        # ── Fase 7: Guardrails ──────────────────────────────────────────
        # 1. Validar nivel de acceso por agente
        from .registry import AgentRegistry
        registry = AgentRegistry()
        validated_agents = []
        user_level = (user_context or {}).get('level', 1)

        for agent_name in agents:
            agent_obj = registry.get_by_name(agent_name)
            if agent_obj:
                required_level = agent_obj.definition.access_level
                if user_level < required_level:
                    logger.warning(
                        f"[Fase7] Agente '{agent_name}' requiere nivel "
                        f"{required_level}, usuario tiene {user_level}. Bloqueado."
                    )
                    state['results'][agent_name] = {
                        'agent_name': agent_name,
                        'success': False,
                        'error_message': (
                            f"Nivel insuficiente: se requiere nivel "
                            f"{required_level} para usar {agent_name}"
                        ),
                        'confidence': 0.0,
                    }
                    continue
            validated_agents.append(agent_name)

        agents = validated_agents
        state['agents_activated'] = agents

        # 2. Budget check: límite de iteraciones estimadas
        MAX_TOTAL_ITERATIONS = 25
        estimated = len(agents) * 5
        if estimated > MAX_TOTAL_ITERATIONS:
            logger.warning(
                f"[Fase7] Presupuesto excedido: {estimated} > "
                f"{MAX_TOTAL_ITERATIONS} iteraciones estimadas"
            )
            agents = agents[:MAX_TOTAL_ITERATIONS // 5]
            state['agents_activated'] = agents

        if not agents:
            logger.warning("[Fase7] No hay agentes válidos después de guardrails")
            state['latencia_total_ms'] = (time.time() - start) * 1000
            state['aggregated_answer'] = {
                'successful': [], 'failed': [],
                'total_agents': 0, 'successful_count': 0, 'failed_count': 0,
            }
            return state

        # ── Paso 2: Ejecutar agentes ──
        if len(agents) == 1:
            # Modo single: ejecución directa
            agent = registry.get_by_name(agents[0])
            if agent:
                result = agent.run(
                    message=message,
                    context={
                        'user_id': user_id,
                        'user_level': (user_context or {}).get('level', 1),
                        'user_context': user_context,
                        'conversation_id': conversation_id,
                        'search_plan': search_plan,
                    },
                )
                state['results'][agents[0]] = result.to_log() if hasattr(result, 'to_log') else {}
        else:
            # Modo paralelo: concurrent.futures
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(agents)) as executor:
                futures = {}
                for agent_name in agents:
                    agent = registry.get_by_name(agent_name)
                    if agent:
                        future = executor.submit(
                            agent.run,
                            message=message,
                            context={
                                'user_id': user_id,
                                'user_level': (user_context or {}).get('level', 1),
                                'user_context': user_context,
                                'conversation_id': conversation_id,
                                'search_plan': search_plan,
                            },
                        )
                        futures[future] = agent_name

                for future in concurrent.futures.as_completed(futures):
                    agent_name = futures[future]
                    try:
                        result = future.result(timeout=30)
                        state['results'][agent_name] = (
                            result.to_log() if hasattr(result, 'to_log') else result
                        )
                    except Exception as e:
                        state['results'][agent_name] = {
                            'agent_name': agent_name,
                            'success': False,
                            'error_message': str(e),
                            'confidence': 0.0,
                        }

        # Paso 3: Agregar resultados (similar a aggregator_node)
        successful = [
            {'name': name, 'data': r}
            for name, r in state['results'].items()
            if r.get('success', False)
        ]
        failed = [
            {'name': name, 'error': r.get('error_message', 'unknown')}
            for name, r in state['results'].items()
            if not r.get('success', False)
        ]

        state['aggregated_answer'] = {
            'successful': successful,
            'failed': failed,
            'total_agents': len(agents),
            'successful_count': len(successful),
            'failed_count': len(failed),
        }
        state['critique_passed'] = len(successful) > 0
        state['latencia_total_ms'] = (time.time() - start) * 1000

        logger.info(
            f"[AgentGraph] Completado: {len(successful)} exitosos, "
            f"{len(failed)} fallidos, "
            f"{state['latencia_total_ms']:.0f}ms"
        )

        return state
