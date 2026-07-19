"""
AgenteMercado — Agente de dominio de mercado y análisis.

Skills que envuelve (ya existentes):
- ReportePreciosZonaSkill
- MetricasMarketingSkill
- CampanasActivasSkill
- ScraperOrchestratorSkill

SPEC: refactor_plataforma_agentes.md — Fase 2
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .base_agent import AgentDefinition, AgentResult, BaseAgent, ReActLoopMixin

logger = logging.getLogger(__name__)


_AGENTE_MERCADO_PROMPT = """Eres el Agente de Mercado de Propifai.
Tu objetivo es analizar el mercado inmobiliario, generar reportes de precios,
y monitorear campañas de marketing.

Tienes acceso a estas skills:
- reporte_precios_zona: reporte de precios por zona y tipo de propiedad
- metricas_marketing: métricas de campañas publicitarias y ROI
- campanas_activas: estado de campañas Meta Ads
- scraper_orchestrator: scraping de portales para datos de competencia

REGLAS:
1. Para preguntas de precios y tendencias, usa reporte_precios_zona
2. Para campañas y marketing, usa metricas_marketing o campanas_activas
3. Los scrapers se usan para datos frescos de competencia
4. Siempre contextualiza los datos con la zona/distrito de Arequipa
5. No inventes cifras — usa SOLO los datos de las skills"""


class AgenteMercado(BaseAgent, ReActLoopMixin):
    """Agente especializado en análisis de mercado y marketing."""

    definition = AgentDefinition(
        name='agente_mercado',
        description=(
            'Agente especializado en análisis de mercado inmobiliario, '
            'reportes de precios por zona, campañas de marketing, '
            'y datos de competencia. Responde consultas como: '
            '"cómo está el mercado en Cayma", "reporte de precios", '
            '"campañas activas de Facebook", "métricas de marketing"'
        ),
        domain='marketing',
        allowed_skills=[
            'reporte_precios_zona',
            'metricas_marketing',
            'campanas_activas',
            'scraper_orchestrator',
        ],
        access_level=2,
        max_iterations=5,
        system_prompt=_AGENTE_MERCADO_PROMPT,
        is_active=True,
        budget_limit_usd=0.05,
    )

    def run(self, message: str, context: Optional[dict] = None) -> AgentResult:
        """Ejecuta el ReAct loop para consultas de mercado."""
        return super().run(message, context)
