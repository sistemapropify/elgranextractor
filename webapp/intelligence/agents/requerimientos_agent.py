"""
AgenteRequerimientos — Agente de dominio de requerimientos y matching.

Skills que envuelve (ya existentes):
- MisRequerimientosSkill
- MatchingOfertaDemandaSkill
- MisMatchesSkill

SPEC: refactor_plataforma_agentes.md — Fase 2
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .base_agent import AgentDefinition, AgentResult, BaseAgent, ReActLoopMixin

logger = logging.getLogger(__name__)


_AGENTE_REQUERIMIENTOS_PROMPT = """Eres el Agente de Requerimientos de Propifai.
Tu objetivo es gestionar requerimientos de clientes y hacer matching
con propiedades disponibles.

Tienes acceso a estas skills:
- mis_requerimientos: consultar requerimientos de clientes
- matching_OD: matching oferta-demanda entre propiedades y requerimientos
- mis_matches: consultar matches generados

REGLAS:
1. Para consultar requerimientos de un cliente específico, usa mis_requerimientos
2. Para cruzar requerimientos con propiedades, usa matching_OD
3. Para ver matches ya generados, usa mis_matches
4. Siempre confirma los detalles antes de hacer matching
5. No inventes datos — usa SOLO la información de las skills"""


class AgenteRequerimientos(BaseAgent, ReActLoopMixin):
    """Agente especializado en requerimientos y matching."""

    definition = AgentDefinition(
        name='agente_requerimientos',
        description=(
            'Agente especializado en requerimientos de clientes, '
            'matching oferta-demanda, y seguimiento de matches. '
            'Responde consultas como: "qué requerimientos tengo", '
            '"cruza mis propiedades con requerimientos", '
            '"tengo matches nuevos", "mis clientes buscando propiedad"'
        ),
        domain='publico',
        allowed_skills=[
            'mis_requerimientos',
            'matching_OD',
            'mis_matches',
        ],
        access_level=1,
        max_iterations=5,
        system_prompt=_AGENTE_REQUERIMIENTOS_PROMPT,
        is_active=True,
        budget_limit_usd=0.05,
    )

    def run(self, message: str, context: Optional[dict] = None) -> AgentResult:
        """Ejecuta el ReAct loop para consultas de requerimientos."""
        return super().run(message, context)
