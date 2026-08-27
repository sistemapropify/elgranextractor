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
from datetime import date, datetime
from decimal import Decimal

from django.db import OperationalError, close_old_connections

logger = logging.getLogger(__name__)
from .shadow_context import (
    draft_event_key,
    draft_identity_key,
    find_trigger_index,
    identity_key,
    message_event_key,
    property_code_as_of,
    shadow_history_before,
)



def _json_safe(value):
    """Convierte valores no serializables a JSON (Decimal, fechas) para poder
    guardarlos en campos JSONField. Los precios/áreas vienen como Decimal de
    SQL Server y rompían el guardado del draft en silencio (ej. 23/08)."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


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
    ``auto_escalation=True`` y respuesta vacía para revisión humana. Tras generar, se validan alucinaciones y
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
        from lead_intelligence.services import (
            get_lead_conversation,
            get_lead_conversation_by_identity,
        )

        try:
            conversation = (
                get_lead_conversation(lead_id)
                if lead_id
                else get_lead_conversation_by_identity(thread_id=thread_id, phone=phone)
            )
        except Exception:  # CRM temporalmente no disponible: continúa sin historial.
            conversation = None
        messages = list((conversation or {}).get("messages") or [])
        resolved_lead_id = (conversation or {}).get("id") or lead_id or 0
        target_index = find_trigger_index(messages, text)
        if target_index is None:
            target_message = {
                "sender": "lead",
                "text": text,
                "timestamp": None,
                "position": len(messages),
            }
            messages.append(target_message)
            target_index = len(messages) - 1
        else:
            target_message = messages[target_index]

        if not property_code:
            property_code = property_code_as_of(messages, target_index)

        wanted_identities = {
            identity_key(lead_id=resolved_lead_id),
            identity_key(thread_id=thread_id, phone=phone),
        }
        try:
            recent_drafts = list(
                BotResponseDraft.objects.using("default")
                .filter(mode=BotResponseDraft.Mode.SHADOW_LIVE)
                .order_by("-created_at", "-id")[:1000]
            )
        except (TypeError, OperationalError):
            recent_drafts = []
        existing_drafts = [
            item
            for item in reversed(recent_drafts)
            if getattr(item, "source_lead_id", 0) == resolved_lead_id
            or draft_identity_key(item) in wanted_identities
        ]
        event_key = message_event_key(
            lead_id=resolved_lead_id,
            thread_id=thread_id,
            phone=phone,
            message=target_message,
            index=target_index,
        )
        duplicate = next(
            (item for item in existing_drafts if draft_event_key(item) == event_key),
            None,
        )
        if duplicate is not None:
            return duplicate
        shadow_history = shadow_history_before(
            messages, target_index, existing_drafts
        )
        event_context = {
            "thread_id": thread_id,
            "phone": phone,
            "event_key": event_key,
            "source_position": target_message.get("position", target_index),
            "source_timestamp": _json_safe(target_message.get("timestamp")),
            "active_property_code": property_code,
        }
        lead_id = resolved_lead_id
        # Un código explícito inicia/cambia la propiedad activa y usa exactamente
        # la misma decisión determinista del respondedor nocturno.
        from n8n_bridge.services.initial_property_config import get_bot_configuration
        from n8n_bridge.services.initial_property_decision import (
            decide_initial_property_response,
        )
        from n8n_bridge.services.initial_property_detector import extract_property_identity

        identity = extract_property_identity(text)
        if identity["codes"]:
            decision = decide_initial_property_response(
                text,
                get_bot_configuration(),
                {"thread_id": thread_id, "phone": phone},
            )
            verified_data = decision.get("data") or {}
            response = decision.get("reply_text") or ""
            reason = decision.get("reason_code") or "DECISION_FAILED"
            draft = BotResponseDraft.objects.using("default").create(
                source_lead_id=lead_id or 0,
                client_message=text,
                intent_category=intent,
                prompt_snapshot={
                    "decision": reason,
                    "evidence": decision.get("evidence") or {},
                    "context": event_context,
                },
                generated_response=response,
                property_data_used=_json_safe(
                    [verified_data] if verified_data else []
                ),
                mode=BotResponseDraft.Mode.SHADOW_LIVE,
                model_version="deterministic-template-v1",
                trace_id="",
                auto_hallucination=False,
                blocked_reason=(
                    "" if decision.get("success") else f"Decisión determinista: {reason}"
                ),
            )
            draft.trace_id = f"bot_draft:{draft.pk}"
            draft.save(using="default", update_fields=["trace_id"])
            return draft



        # Escalamiento: nunca generar con IA (spec §7).
        if is_escalation(text):
            draft = BotResponseDraft.objects.using("default").create(
                source_lead_id=lead_id or 0,
                client_message=text,
                intent_category=intent,
                prompt_snapshot={
                    "guardrail": "escalamiento",
                    "context": event_context,
                },
                generated_response="",
                property_data_used=[],
                mode=BotResponseDraft.Mode.SHADOW_LIVE,
                model_version=LLMService.DEEPSEEK_MODEL,
                trace_id=f"bot_draft:{0}",
                auto_escalation=True,
                blocked_reason="Mensaje de escalamiento/riesgo legal: requiere revisión humana",
            )
            draft.trace_id = f"bot_draft:{draft.pk}"
            draft.save(using="default", update_fields=["trace_id"])
            return draft

        # TODO lead entrante DEBE generar un borrador visible. El borrador se
        # crea PRIMERO (con contexto mínimo) para que, si el armado del prompt
        # o la llamada IA fallan, el borrador quede en la cola marcado con el
        # error (blocked_reason) en lugar de desaparecer en silencio (como
        # pasó el 23/08, cuando entraron leads y el Motor IA no creó nada).
        draft = BotResponseDraft.objects.using("default").create(
            source_lead_id=lead_id or 0,
            client_message=text,
            intent_category=intent,
            prompt_snapshot={"context": event_context},
            generated_response="",
            property_data_used=[],
            mode=BotResponseDraft.Mode.SHADOW_LIVE,
            model_version=LLMService.DEEPSEEK_MODEL,
            trace_id="",
        )
        draft.trace_id = f"bot_draft:{draft.pk}"
        draft.save(using="default", update_fields=["trace_id"])

        # Armado de contexto (propiedad/RAG/memoria) para el prompt.
        try:
            assembled = PromptAssemblyService.assemble(
                client_message=text,
                intent_category=intent,
                property_code=property_code,
                lead_id=lead_id,
                thread_id=thread_id,
                phone=phone,
                conversation_messages=shadow_history,
            )
            draft.intent_category = assembled["intent_category"] or intent
            # Sanitizar a JSON-safe: SQL Server devuelve Decimal (precios) que
            # rompía el guardado del draft en silencio.
            draft.property_data_used = _json_safe(assembled["property_data_used"])
            draft.prompt_snapshot = {
                "system_prompt": assembled["system_prompt"],
                "user_prompt": assembled["user_prompt"],
                "few_shot": assembled["few_shot"],
                "context": event_context,
            }
            draft.save(
                using="default",
                update_fields=["intent_category", "property_data_used", "prompt_snapshot"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "shadow_live: falló el armado de contexto (draft=%s, thread=%s)",
                draft.pk, thread_id,
            )
            draft.blocked_reason = (
                f"Fallo al armar contexto del borrador: {type(exc).__name__}: {exc}"
            )
            draft.save(using="default", update_fields=["blocked_reason"])
            return draft

        # Las repreguntas factuales de una propiedad no se delegan al LLM:
        # el agente ya consultó la ficha viva y el selector determinista limita
        # la respuesta exactamente a los campos solicitados.
        strict_response = str(assembled.get("strict_response") or "").strip()
        if strict_response:
            draft.generated_response = strict_response
            draft.model_version = "deterministic-property-fact-v1"
            draft.save(
                using="default",
                update_fields=["generated_response", "model_version"],
            )
            return draft

        token = bind_trace_id(f"bot_draft:{draft.pk}")
        try:
            ok, msg, response = LLMService.generate_response(
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
        else:
            # El Motor IA respondió con error: el borrador se deja visible y
            # marcado (el lead no se pierde en silencio).
            draft.blocked_reason = (
                f"El Motor IA no generó respuesta: {msg or 'sin mensaje'}"
            )
            draft.save(using="default", update_fields=["blocked_reason"])
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
