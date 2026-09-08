"""Orquestador determinista one-shot del primer contacto nocturno."""

import hashlib
import hmac
import logging
import time
from datetime import date, datetime, timedelta
from math import ceil
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from n8n_bridge.models import PropertyBotInitialResponse

from .initial_property_config import get_bot_configuration, schedule_state
from .initial_property_detector import detect_captacion_intent
from .initial_property_decision import decide_initial_property_response
from .initial_property_memory import save_initial_episode
from .initial_property_renderer import render_captacion_response


logger = logging.getLogger(__name__)


def _json_safe(value):
    """Convierte recursivamente valores no serializables (Decimal, fechas)
    a JSON-safe antes de persistirlos en campos JSONField o en memoria."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def phone_digest(phone):
    normalized = "".join(ch for ch in str(phone or "") if ch.isdigit())
    digest = hmac.new(
        str(settings.SECRET_KEY).encode(), normalized.encode(), hashlib.sha256
    ).hexdigest()
    return normalized, digest


def _serialize_schedule(state):
    return {
        "timezone": state["timezone"],
        "start": state["start"],
        "end": state["end"],
        "local_now": state["local_now"].isoformat(),
        "inside": state["inside"],
    }


def _response_from_record(record, duplicate=False):
    scheduled = record.reason_code == "CAPTACION_SCHEDULED"
    response = {
        "success": True,
        "action": record.action,
        # Una captación programada no entrega todavía el texto: n8n debe
        # confirmarla al vencer el plazo, después de revisar si respondió un humano.
        "reply_text": record.response_text if record.action == "respond_once" and not scheduled else "",
        "reason_code": "DUPLICATE_MESSAGE" if duplicate else record.reason_code,
        "interaction_id": str(record.id),
        "property_code": record.property_code,
        "bot_finished_for_conversation": record.action == "respond_once",
    }
    send_not_before = (record.evidence or {}).get("send_not_before")
    if send_not_before:
        try:
            scheduled_at = datetime.fromisoformat(send_not_before)
            remaining = max(0, ceil((scheduled_at - timezone.now()).total_seconds()))
        except (TypeError, ValueError):
            remaining = 0
        response.update(
            {
                "delivery_mode": "delayed",
                "delay_seconds": remaining,
                "configured_delay_seconds": (record.evidence or {}).get(
                    "configured_delay_seconds", remaining
                ),
                "send_not_before": send_not_before,
                "delivery_ready": False,
                "cancel_if_agent_replied": True,
            }
        )
    else:
        response.update({"delivery_mode": "immediate", "delay_seconds": 0})
    return response


def confirm_scheduled_captacion(interaction_id, conversation_has_agent_reply):
    """Libera o cancela una captación al vencer su espera.

    El integrador debe consultar la conversación justo antes de llamar esta
    función y declarar si ya existe una respuesta de cualquier agente humano.
    """
    with transaction.atomic():
        record = PropertyBotInitialResponse.objects.select_for_update().get(
            id=interaction_id
        )
        if record.reason_code == "CAPTACION_CANCELLED_AGENT_REPLIED":
            return _response_from_record(record)
        if record.reason_code == "CAPTACION_SENT":
            response = _response_from_record(record)
            response["delivery_ready"] = True
            return response
        if record.reason_code != "CAPTACION_SCHEDULED":
            raise ValueError("La interacción no es una captación programada")

        if conversation_has_agent_reply:
            record.action = "ignore"
            record.reason_code = "CAPTACION_CANCELLED_AGENT_REPLIED"
            record.evidence = {**(record.evidence or {}), "cancelled_by_agent_reply": True}
            record.save(update_fields=["action", "reason_code", "evidence"])
            response = _response_from_record(record)
            response.update({"delivery_mode": "cancelled", "delivery_ready": False})
            return response

        send_not_before = datetime.fromisoformat(record.evidence["send_not_before"])
        if timezone.now() < send_not_before:
            return _response_from_record(record)

        record.reason_code = "CAPTACION_SENT"
        record.responded_at = timezone.now()
        record.save(update_fields=["reason_code", "responded_at"])
        response = _response_from_record(record)
        response.update({"delivery_mode": "immediate", "delivery_ready": True, "delay_seconds": 0})
        return response


def process_initial_message(payload):
    """Procesa el primer mensaje de un hilo con lógica real one-shot."""
    started = time.monotonic()
    message_id = str(payload.get("message_id") or "").strip()
    text = str(payload.get("text") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    external_id = str(payload.get("external_conversation_id") or "").strip()
    contact_name = str(payload.get("contact_name") or "").strip()

    # Modo shadow_live (opcional, RESPONSE_INTELLIGENCE_SHADOW=1): genera un
    # borrador IA mediante la cola SQL, sin enviar nada ni alterar esta respuesta.
    if text:
        try:
            from response_intelligence.shadow import spawn_shadow_draft

            spawn_shadow_draft(
                source_event_id=message_id,
                client_message=text,
                thread_id=external_id or phone,
                phone=phone,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("shadow.enqueue_failed error_type=%s", type(exc).__name__)

    existing = PropertyBotInitialResponse.objects.filter(message_id=message_id).first()
    if existing:
        return _response_from_record(existing, duplicate=True)

    normalized_phone, digest = phone_digest(phone)
    config = get_bot_configuration()
    schedule = schedule_state(config)
    fallback_thread = f"phone:{digest}:{schedule['local_now'].date().isoformat()}"
    thread_id = external_id or fallback_thread

    previous = PropertyBotInitialResponse.objects.filter(
        external_conversation_id=thread_id,
        action="respond_once",
    ).first()
    if previous:
        return _persist_ignore(
            message_id, thread_id, digest, normalized_phone, text, config, schedule,
            "ALREADY_RESPONDED", started, contact_name=contact_name,
        )
    if payload.get("human_takeover") is True:
        return _persist_ignore(message_id, thread_id, digest, normalized_phone, text, config, schedule, "HUMAN_TAKEOVER", started, contact_name=contact_name)
    if not config.enabled:
        return _persist_ignore(message_id, thread_id, digest, normalized_phone, text, config, schedule, "BOT_DISABLED", started, contact_name=contact_name)
    if not schedule["inside"]:
        return _persist_ignore(message_id, thread_id, digest, normalized_phone, text, config, schedule, "OUTSIDE_SCHEDULE", started, contact_name=contact_name)
    if config.require_external_conversation_id and not external_id:
        return _persist_ignore(message_id, thread_id, digest, normalized_phone, text, config, schedule, "MISSING_CONVERSATION_ID", started, contact_name=contact_name)

    # ── Captación: el cliente quiere VENDER una propiedad (no trae código PROP).
    # Se atiende ANTES del chequeo de código para que estos leads reciban
    # respuesta (hoy caían en NO_PROPERTY_CODE y se ignoraban).
    if detect_captacion_intent(text):
        reply = render_captacion_response(config)
        delay_seconds = config.captacion_delay_seconds
        send_not_before = timezone.now() + timedelta(seconds=delay_seconds)
        latency = round((time.monotonic() - started) * 1000)
        conversation_key = f"thread:{thread_id}"
        try:
            with transaction.atomic():
                record = PropertyBotInitialResponse.objects.create(
                    message_id=message_id,
                    external_conversation_id=thread_id,
                    conversation_property_key=conversation_key,
                    phone_hash=digest,
                    phone_last4=normalized_phone[-4:],
                    phone=normalized_phone,
                    contact_name=contact_name,
                    incoming_text=text[:2000],
                    response_text=reply,
                    action="respond_once",
                    reason_code="CAPTACION_SCHEDULED",
                    evidence={
                        "lead_type": "captacion",
                        "intent": "vender",
                        "configured_delay_seconds": delay_seconds,
                        "send_not_before": send_not_before.isoformat(),
                    },
                    bot_enabled=config.enabled,
                    schedule_snapshot=_serialize_schedule(schedule),
                    latency_ms=latency,
                    responded_at=None,
                    review_status="pending",
                )
        except IntegrityError:
            record = PropertyBotInitialResponse.objects.filter(
                external_conversation_id=thread_id, action="respond_once"
            ).first()
            if record:
                return _response_from_record(record, duplicate=True)
            raise
        episode = save_initial_episode(
            phone, contact_name, text, reply,
            {"lead_type": "captacion", "intent": "vender"},
        )
        if episode and episode.get("id"):
            record.episode_id = episode["id"]
            record.save(update_fields=["episode_id"])
        return _response_from_record(record)

    decision = decide_initial_property_response(text, config)
    if not decision["success"]:
        return _persist_ignore(
            message_id, thread_id, digest, normalized_phone, text, config, schedule,
            decision["reason_code"], started, property_code=decision["property_code"],
            evidence=decision["evidence"], contact_name=contact_name,
        )
    data = decision["data"]
    data_clean = _json_safe(data)
    reply = decision["reply_text"]

    latency = round((time.monotonic() - started) * 1000)
    conversation_key = f"thread:{thread_id}"
    try:
        with transaction.atomic():
            record = PropertyBotInitialResponse.objects.create(
                message_id=message_id,
                external_conversation_id=thread_id,
                conversation_property_key=conversation_key,
                phone_hash=digest,
                phone_last4=normalized_phone[-4:],
                phone=normalized_phone,
                contact_name=contact_name,
                property_id=data["property_id"],
                property_code=data["code"],
                property_type=data["property_type"],
                incoming_text=text[:2000],
                response_text=reply,
                action="respond_once",
                reason_code="ANSWER_SENT",
                evidence=data_clean,
                bot_enabled=config.enabled,
                schedule_snapshot=_serialize_schedule(schedule),
                latency_ms=latency,
                responded_at=timezone.now(),
                review_status="pending",
            )
    except IntegrityError:
        record = PropertyBotInitialResponse.objects.filter(
            external_conversation_id=thread_id, action="respond_once"
        ).first()
        if record:
            return _response_from_record(record, duplicate=True)
        raise

    episode = save_initial_episode(phone, contact_name, text, reply, data_clean)
    if episode and episode.get("id"):
        record.episode_id = episode["id"]
        record.save(update_fields=["episode_id"])
    return _response_from_record(record)


def _persist_ignore(message_id, thread_id, digest, normalized_phone, text, config, schedule, reason, started, property_code="", evidence=None, contact_name=""):
    latency = round((time.monotonic() - started) * 1000)
    try:
        record = PropertyBotInitialResponse.objects.create(
            message_id=message_id,
            external_conversation_id=thread_id,
            conversation_property_key=f"message:{message_id}",
            phone_hash=digest,
            phone_last4=normalized_phone[-4:],
            phone=normalized_phone,
            contact_name=contact_name,
            property_code=property_code,
            incoming_text=text[:2000],
            action="ignore",
            reason_code=reason,
            evidence=_json_safe(evidence or {}),
            bot_enabled=config.enabled,
            schedule_snapshot=_serialize_schedule(schedule),
            latency_ms=latency,
            review_status="pending" if reason in {"TITLE_CODE_MISMATCH", "MISSING_REQUIRED_DATA", "INTERNAL_ERROR"} else "not_required",
        )
    except IntegrityError:
        record = PropertyBotInitialResponse.objects.get(message_id=message_id)
    return _response_from_record(record)
