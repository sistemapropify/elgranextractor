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
) -> PILAgentState:
    """Crea un estado inicial para el grafo."""
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
    ) -> PILAgentState:
        """
        Ejecuta el grafo completo.

        Args:
            message: Mensaje del usuario
            conversation_id: ID de la conversación
            user_id: ID del usuario (opcional)
            contexto_activo: Contexto del turno anterior (opcional)

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
        )
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
