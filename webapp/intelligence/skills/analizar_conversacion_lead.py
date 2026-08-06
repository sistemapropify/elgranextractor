"""Skill for evidence-backed contextual analysis of a complete lead chat."""

from typing import Any, Dict, Optional

from intelligence.skills.base import BaseSkill, SkillResult
from lead_intelligence.contextual_analysis import analyze_conversation_context


class AnalizarConversacionLeadSkill(BaseSkill):
    name = "analizar_conversacion_lead"
    description = (
        "Analiza el contexto completo de chat_history de un lead y determina "
        "calificación e intención real de visita con evidencia del cliente."
    )
    category = "crm"
    access_level = 3
    required_domain = "marketing"
    parameters_schema = {
        "messages": {
            "type": "array",
            "description": "Mensajes normalizados y ordenados de la conversación.",
            "required": False,
        },
        "lead_id": {
            "type": "integer",
            "description": "ID del lead cuando la conversación debe obtenerse del CRM en modo SELECT.",
            "required": False,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return isinstance(params, dict) and (
            isinstance(params.get("messages"), list) or params.get("lead_id")
        )

    def execute(
        self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        if not self.validate_params(params):
            return SkillResult.error(
                "Se requiere la conversación completa en 'messages'.",
                skill_name=self.name,
            )
        messages = params.get("messages")
        if messages is None:
            from lead_intelligence.services import get_lead_conversation

            lead = get_lead_conversation(int(params["lead_id"]))
            if lead is None:
                return SkillResult.error("Lead no encontrado.", skill_name=self.name)
            messages = lead["messages"]
        try:
            assessment = analyze_conversation_context(messages)
        except Exception as exc:
            return SkillResult.error(str(exc), skill_name=self.name)
        return SkillResult.ok(
            data=assessment,
            message="Conversación analizada con evidencia contextual.",
            metadata={
                "analysis_version": assessment["analysis_version"],
                "model_version": assessment["model_version"],
            },
            skill_name=self.name,
        )
