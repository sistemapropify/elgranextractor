"""Agent for evidence-backed lead conversation intelligence."""

from typing import Optional

from .base_agent import AgentDefinition, AgentResult, BaseAgent, ReActLoopMixin


_PROMPT = """Eres el Agente de Inteligencia de Leads de Prometeo.
Analizas conversaciones completas y explicas calificación e intención real
de visita usando únicamente evidencia escrita por el lead.

Usa analizar_conversacion_lead para un lead específico. Distingue siempre
lo dicho por el lead de las propuestas del agente. Pedir precio, ubicación
o características no demuestra intención de visita. Si falta evidencia,
responde no confirmado o ambiguo. dbpropify_be es de solo lectura."""


class AgenteInteligenciaLeads(ReActLoopMixin, BaseAgent):
    definition = AgentDefinition(
        name="agente_inteligencia_leads",
        description=(
            "Analiza calificación, intención de visita y calidad de "
            "conversaciones completas de leads con evidencia verificable."
        ),
        domain="marketing",
        allowed_skills=["analizar_conversacion_lead"],
        access_level=3,
        max_iterations=3,
        system_prompt=_PROMPT,
        is_active=True,
        budget_limit_usd=0.05,
    )

    def run(self, message: str, context: Optional[dict] = None) -> AgentResult:
        return super().run(message, context)
