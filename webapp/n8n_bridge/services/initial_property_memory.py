"""Escritura de memoria episódica para la evolución futura del embudo."""

import logging

from intelligence.services.chat_processor import ChatProcessor
from intelligence.services.episodic_memory import EpisodicMemoryService



logger = logging.getLogger(__name__)
APP_ID = "whatsapp-property-funnel"


def save_initial_episode(phone, contact_name, incoming_text, response_text, evidence):
    try:
        from n8n_bridge.views import _get_or_create_lead

        lead = _get_or_create_lead(phone, contact_name)
        conversation = ChatProcessor._get_or_create_conversation(user=lead, app_id=APP_ID)
        return EpisodicMemoryService.save_episode(
            user_id=lead.id,
            conversation_id=conversation.id,
            user_message=incoming_text,
            assistant_response=response_text,
            episode_type="property_detail",
            intent_detected="initial_property_interest",
            context={
                "channel": "whatsapp_property_funnel",
                "funnel_stage": "waiting_for_human",
                **evidence,
            },
            rag_context_used={},
            memory_context_used={},
            generate_embedding=False,
        )
    except Exception:
        logger.exception("No se pudo guardar el episodio inicial de WhatsApp")
        return None
