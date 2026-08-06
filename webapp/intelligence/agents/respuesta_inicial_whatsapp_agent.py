"""Agente determinista de una sola intervención para WhatsApp."""

from .base_agent import AgentDefinition, AgentResult, BaseAgent
from ..skills.propiedades.informacion_inicial_propiedad import InformacionInicialPropiedadSkill


class AgenteRespuestaInicialWhatsApp(BaseAgent):
    definition = AgentDefinition(
        name="agente_respuesta_inicial_whatsapp",
        description="Responde una sola vez el contacto inicial nocturno de una publicación",
        domain="publico",
        allowed_skills=["informacion_inicial_propiedad"],
        access_level=1,
        max_iterations=1,
        system_prompt="",
        is_active=True,
        budget_limit_usd=0.0,
    )

    def resolve(self, property_code, context=None):
        return InformacionInicialPropiedadSkill().execute(
            {"property_code": property_code},
            context or {},
        )

    def run(self, message, context=None):
        context = context or {}
        result = self.resolve(context.get("property_code"), context)
        return AgentResult(
            agent_name=self.definition.name,
            success=result.success,
            final_answer=result.data if result.success else None,
            iterations_used=1,
            error_message=None if result.success else result.message,
            confidence=1.0 if result.success else 0.0,
        )
