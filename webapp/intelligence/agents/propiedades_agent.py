"""
AgentePropiedades — Agente de dominio de propiedades.

Skills que envuelve (ya existentes):
- BusquedaPropiedadesSkill
- BusquedaExactaSkill
- HybridMatchingSkill
- ACMAnalisisSkill

SPEC: refactor_plataforma_agentes.md — Fase 2
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .base_agent import AgentDefinition, AgentResult, BaseAgent, ReActLoopMixin

logger = logging.getLogger(__name__)


_AGENTE_PROPIEDADES_PROMPT = """Eres el Agente de Propiedades de Propifai.
Tu objetivo es encontrar propiedades que coincidan con lo que pide el usuario.

Tienes acceso a estas skills:
- busqueda_propiedades: búsqueda semántica con filtros (tipo, distrito, precio)
- busqueda_exacta: búsqueda por filtros exactos cuando el usuario da valores precisos
- matching_hibrido: matching inteligente oferta-demanda con embeddings
- acm_analisis: Análisis Comparativo de Mercado para estimar valor de propiedades

REGLAS:
1. Siempre intenta primero con busqueda_propiedades o busqueda_exacta
2. Si el resultado tiene pocos datos, prueba con otra skill o ajusta parámetros
3. Si el usuario pide análisis de valor, usa acm_analisis
4. Si hay parámetros ambiguos, usa la skill más flexible primero
5. No inventes propiedades — usa SOLO los datos de las skills"""


class AgentePropiedades(BaseAgent, ReActLoopMixin):
    """Agente especializado en búsqueda y análisis de propiedades."""

    definition = AgentDefinition(
        name='agente_propiedades',
        description=(
            'Agente especializado en encontrar propiedades (venta/alquiler), '
            'analizar precios de mercado, y hacer matching oferta-demanda. '
            'Responde consultas como: "busco departamento en Cayma", '
            '"casa de 3 dormitorios en Yanahuara", "terrenos para construir", '
            '"análisis de mercado en Cerro Colorado"'
        ),
        domain='publico',
        allowed_skills=[
            'busqueda_propiedades',
            'busqueda_exacta',
            'matching_hibrido',
            'acm_analisis',
        ],
        access_level=1,
        max_iterations=5,
        system_prompt=_AGENTE_PROPIEDADES_PROMPT,
        is_active=True,
        budget_limit_usd=0.05,
    )

    def run(self, message: str, context: Optional[dict] = None) -> AgentResult:
        """Ejecuta el ReAct loop para consultas de propiedades."""
        return super().run(message, context)
