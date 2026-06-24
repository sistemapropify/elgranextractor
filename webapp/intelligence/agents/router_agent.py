"""
RouterAgent — Clasifica la intención del usuario usando SemanticRouter.

F2-001 (6.3): Nodo inicial del grafo LangGraph.
Determina si el mensaje activa una skill o va a RAG puro.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class RouterAgent:
    """
    Clasifica mensajes del usuario usando el SemanticSkillRouter.
    
    Singleton para mantener embeddings de templates cacheados entre llamadas.
    
    Este agente es el punto de entrada del grafo LangGraph. Decide si:
    - Hay una skill que ejecutar (busqueda_propiedades, acm, etc.)
    - Es RAG puro (consulta general sin skill específica)
    """

    _router_instance = None

    @classmethod
    def _get_router(cls):
        """Obtiene instancia singleton del router con templates pre-calculados."""
        if cls._router_instance is None:
            from ..services.semantic_router import SemanticSkillRouter
            cls._router_instance = SemanticSkillRouter()
            # Pre-calcular embeddings de templates para evitar score=0
            cls._router_instance.precompute_all_embeddings()
        return cls._router_instance

    @classmethod
    def run(cls, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta el routing semántico sobre el mensaje del usuario.

        Args:
            state: Dict con al menos 'message'

        Returns:
            state actualizado con skill_detectada, score_routing, threshold
        """
        start = time.time()
        message = state.get('message', '')

        if not message or not message.strip():
            state['skill_detectada'] = None
            state['score_routing'] = 0.0
            state['threshold'] = 0.45
            state['router_latency_ms'] = 0.0
            return state

        try:
            router = cls._get_router()
            result = router.classify(message)

            state['skill_detectada'] = result.skill_name
            state['score_routing'] = result.score
            state['threshold'] = result.threshold
            state['router_latency_ms'] = result.latency_ms
            state['matched_template'] = result.matched_template
            state['fallback_used'] = result.fallback_used

            elapsed = (time.time() - start) * 1000
            logger.info(
                f"[F2-001] RouterAgent: message='{message[:60]}...' | "
                f"skill={result.skill_name} | score={result.score:.4f} | "
                f"threshold={result.threshold} | accepted={result.accepted} | "
                f"latency={elapsed:.1f}ms"
            )

        except Exception as e:
            logger.error(f"[F2-001] RouterAgent error: {e}")
            state['skill_detectada'] = None
            state['score_routing'] = 0.0
            state['threshold'] = 0.45
            state['router_latency_ms'] = 0.0

        return state
