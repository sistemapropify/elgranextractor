"""Modo shadow_live: genera un borrador IA en paralelo sin enviar nada.

El bot determinista de plantillas sigue respondiendo exactamente igual; este
módulo solo crea un ``BotResponseDraft(mode='shadow_live')`` en la BD ``default``
para auditar en silencio lo que el motor IA habría respondido.
Se activa con la variable de entorno RESPONSE_INTELLIGENCE_SHADOW=1 (default off)
y nunca lanza: cualquier fallo solo se registra (la migración debe estar aplicada).
"""

import logging
import os
import threading

logger = logging.getLogger(__name__)


def shadow_mode_enabled() -> bool:
    value = os.environ.get("RESPONSE_INTELLIGENCE_SHADOW", "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def maybe_generate_shadow_draft(
    *,
    lead_id=None,
    client_message="",
    thread_id="",
    intent_category="",
    property_code="",
):
    """Genera un draft shadow_live de forma segura (nunca lanza)."""
    if not shadow_mode_enabled():
        return None
    if not client_message or not str(client_message).strip():
        return None
    try:
        from intelligence.learning.trace_context import bind_trace_id, release_trace_id
        from intelligence.services.llm import LLMService

        from .curation import CurationService
        from .models import BotResponseDraft
        from .prompt_assembly import PromptAssemblyService

        text = str(client_message).strip()[:2000]
        intent = intent_category or CurationService._detect_category(text)
        assembled = PromptAssemblyService.assemble(
            client_message=text,
            intent_category=intent,
            property_code=property_code,
        )
        draft = BotResponseDraft.objects.using("default").create(
            source_lead_id=lead_id or 0,
            client_message=text,
            intent_category=assembled["intent_category"] or intent,
            prompt_snapshot={
                "system_prompt": assembled["system_prompt"],
                "user_prompt": assembled["user_prompt"],
                "few_shot": assembled["few_shot"],
            },
            generated_response="",
            property_data_used=assembled["property_data_used"],
            mode=BotResponseDraft.Mode.SHADOW_LIVE,
            model_version=LLMService.DEEPSEEK_MODEL,
            trace_id="",
        )
        draft.trace_id = f"bot_draft:{draft.pk}"
        draft.save(using="default", update_fields=["trace_id"])

        token = bind_trace_id(f"bot_draft:{draft.pk}")
        try:
            ok, _msg, response = LLMService.generate_response(
                system_prompt=assembled["system_prompt"],
                user_prompt=assembled["user_prompt"],
                max_tokens=600,
            )
        finally:
            release_trace_id(token)
        if ok:
            draft.generated_response = response
            draft.save(using="default", update_fields=["generated_response"])
        return draft
    except Exception as exc:  # noqa: BLE001
        logger.warning("shadow_live no generó borrador (thread=%s): %s", thread_id, exc)
        return None


def spawn_shadow_draft(**kwargs):
    """Lanza la generación en un hilo daemon para no bloquear la respuesta real."""
    try:
        thread = threading.Thread(
            target=maybe_generate_shadow_draft,
            kwargs=kwargs,
            daemon=True,
        )
        thread.start()
        return thread
    except Exception:  # noqa: BLE001
        return None
