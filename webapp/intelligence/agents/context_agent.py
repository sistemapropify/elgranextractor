"""
ContextAgent — Resuelve contexto conversacional y memoria.

F2-001 (6.5): Nodo opcional del grafo LangGraph.
Se salta si es el primer turno (no hay contexto activo previo).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ContextAgent:
    """
    Recupera y aplica contexto conversacional.
    
    Responsabilidades:
    - Obtener contexto activo de la conversación actual
    - Recuperar hechos del usuario (memoria de largo plazo)
    - Obtener episodios relevantes (memoria episódica)
    - Combinar filtros de contexto con parámetros nuevos
    """

    @classmethod
    def run(cls, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta resolución de contexto.

        Args:
            state: Dict con conversation_id, message, contexto_activo

        Returns:
            state actualizado con contexto resuelto y memoria
        """
        start = time.time()
        conversation_id = state.get('conversation_id')
        message = state.get('message', '')
        contexto_activo = state.get('contexto_activo', {})

        try:
            from ..services.context_manager import ContextManager
            from ..services.memory import MemoryService

            # 1. Obtener contexto activo desde ContextManager
            cm = ContextManager()
            contexto = cm.get_active_context(conversation_id)

            # 2. Si hay contexto activo, combinarlo con los parámetros actuales
            if contexto:
                logger.info(
                    f"[F2-001] ContextAgent: contexto activo encontrado: "
                    f"{contexto}"
                )
                # Los parámetros nuevos sobrescriben los del contexto
                params_existentes = state.get('params_extraidos', {})
                # ActiveContext es un dataclass, no un dict.
                # Se convierte a dict con to_dict() antes de combinarlo.
                contexto_dict = contexto.to_dict() if hasattr(contexto, 'to_dict') else {}
                params_combinados = {**contexto_dict, **params_existentes}
                state['params_extraidos'] = params_combinados
                state['contexto_resuelto'] = True
            else:
                state['contexto_resuelto'] = False

            # 3. Recuperar hechos del usuario
            user_id = state.get('user_id')
            if user_id:
                try:
                    memory = MemoryService()
                    hechos = memory.get_user_facts(user_id)
                    state['hechos_usuario'] = hechos
                    if hechos:
                        logger.debug(
                            f"[F2-001] ContextAgent: {len(hechos)} hechos "
                            f"recuperados para usuario {user_id}"
                        )
                except Exception as mem_err:
                    logger.warning(
                        f"[F2-001] ContextAgent: error recuperando hechos: "
                        f"{mem_err}"
                    )

            elapsed = (time.time() - start) * 1000
            logger.info(
                f"[F2-001] ContextAgent: conv={conversation_id} | "
                f"contexto_activo={bool(contexto)} | "
                f"params_combinados={bool(state.get('params_extraidos'))} | "
                f"latencia={elapsed:.1f}ms"
            )

        except Exception as e:
            logger.error(f"[F2-001] ContextAgent error: {e}")

        return state
