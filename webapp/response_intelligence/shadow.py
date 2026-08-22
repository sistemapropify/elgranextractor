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

from django.db import OperationalError, close_old_connections

logger = logging.getLogger(__name__)


def shadow_mode_enabled() -> bool:
    """¿Está activo el shadow_live?

    Prioridad: el interruptor persistente (MotorAIControl, BD ``default``) si
    existe una fila; si no existe, cae a la variable de entorno
    ``RESPONSE_INTELLIGENCE_SHADOW``. Así el switch del dashboard manda sin
    reiniciar el proceso.
    """
    try:
        from .models import MotorAIControl

        control = MotorAIControl.objects.using("default").first()
        if control is not None:
            return bool(control.shadow_live_enabled)
    except Exception:  # noqa: BLE001 - la BD puede no estar disponible aún
        pass
    value = os.environ.get("RESPONSE_INTELLIGENCE_SHADOW", "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _generate_shadow_draft_once(
    *,
    lead_id=None,
    client_message="",
    thread_id="",
    intent_category="",
    property_code="",
    phone="",
):
    """Genera un draft shadow_live de forma segura (nunca lanza).

    Guardrails (spec §7): si el mensaje del cliente es de escalamiento/riesgo
    legal, el motor NUNCA genera con IA — se registra el draft con
    ``auto_escalation=True`` y respuesta vacía (la plantilla sigue respondiendo
    con "un agente te contactará"). Tras generar, se validan alucinaciones y
    negociación de precio con regex.

    Un ``OperationalError`` (corte ODBC transitorio) se propaga para que el
    wrapper ``maybe_generate_shadow_draft`` cierre conexiones y reintente una vez.
    """
    if not shadow_mode_enabled():
        return None
    if not client_message or not str(client_message).strip():
        return None
    try:
        from intelligence.learning.trace_context import bind_trace_id, release_trace_id
        from intelligence.services.llm import LLMService

        from .curation import CurationService
        from .guardrails import block_summary, is_escalation, validate_generated_response
        from .models import BotResponseDraft
        from .prompt_assembly import PromptAssemblyService

        text = str(client_message).strip()[:2000]
        intent = intent_category or CurationService._detect_category(text)

        # Escalamiento: nunca generar con IA (spec §7).
        if is_escalation(text):
            draft = BotResponseDraft.objects.using("default").create(
                source_lead_id=lead_id or 0,
                client_message=text,
                intent_category=intent,
                prompt_snapshot={
                    "guardrail": "escalamiento",
                    "context": {"thread_id": thread_id, "phone": phone},
                },
                generated_response="",
                property_data_used=[],
                mode=BotResponseDraft.Mode.SHADOW_LIVE,
                model_version=LLMService.DEEPSEEK_MODEL,
                trace_id=f"bot_draft:{0}",
                auto_escalation=True,
                blocked_reason="Mensaje de escalamiento/riesgo legal: la plantilla responde con aviso a agente",
            )
            draft.trace_id = f"bot_draft:{draft.pk}"
            draft.save(using="default", update_fields=["trace_id"])
            return draft

        # shadow_live: SOLO LECTURA de la memoria (no se escribe el borrador
        # porque no se envía). El contexto se lee aislado en app motor-ia-whatsapp.
        assembled = PromptAssemblyService.assemble(
            client_message=text,
            intent_category=intent,
            property_code=property_code,
            lead_id=lead_id,
            thread_id=thread_id,
        )
        draft = BotResponseDraft.objects.using("default").create(
            source_lead_id=lead_id or 0,
            client_message=text,
            intent_category=assembled["intent_category"] or intent,
            prompt_snapshot={
                "system_prompt": assembled["system_prompt"],
                "user_prompt": assembled["user_prompt"],
                "few_shot": assembled["few_shot"],
                # Contexto del hilo/teléfono para que el revisor sepa de qué
                # lead proviene el draft (los drafts del primer mensaje no
                # tienen lead_id en el CRM todavía).
                "context": {"thread_id": thread_id, "phone": phone},
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
            # Validación determinista post-generación (spec §7).
            validation = validate_generated_response(
                response, draft.property_data_used
            )
            draft.auto_hallucination = validation["hallucination"]
            draft.auto_discount = validation["discount"]
            if validation["blocked"]:
                draft.blocked_reason = block_summary(validation)
            draft.save(
                using="default",
                update_fields=[
                    "generated_response",
                    "trace_id",
                    "auto_hallucination",
                    "auto_discount",
                    "blocked_reason",
                ],
            )
        return draft
    except OperationalError:
        # Se propaga para que el wrapper reintente con una conexión nueva.
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("shadow_live no generó borrador (thread=%s): %s", thread_id, exc)
        return None


def maybe_generate_shadow_draft(
    *,
    lead_id=None,
    client_message="",
    thread_id="",
    intent_category="",
    property_code="",
    phone="",
):
    """Genera un draft shadow_live en un hilo daemon de forma robusta.

    El hilo daemon no hereda la conexión del request; al correr tras devolver
    la respuesta, la conexión ODBC del worker puede estar cerrada o cortarse
    de forma transitoria. Se fuerza una conexión nueva y, ante un corte ODBC,
    se reintenta una vez (mismo patrón que el dashboard), para que el borrador
    no se pierda silenciosamente.
    """
    if not client_message or not str(client_message).strip():
        return None
    for attempt in range(2):
        try:
            close_old_connections()
        except Exception:  # noqa: BLE001
            pass
        try:
            return _generate_shadow_draft_once(
                lead_id=lead_id,
                client_message=client_message,
                thread_id=thread_id,
                intent_category=intent_category,
                property_code=property_code,
                phone=phone,
            )
        except OperationalError:
            if attempt:
                logger.warning(
                    "shadow_live: corte ODBC persistente, borrador no generado (thread=%s)",
                    thread_id,
                )
                return None
            logger.warning(
                "shadow_live: corte ODBC en hilo, reintentando (thread=%s)",
                thread_id,
            )
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
