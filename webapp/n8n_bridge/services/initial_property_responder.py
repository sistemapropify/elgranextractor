"""Orquestador determinista one-shot del primer contacto nocturno."""

import hashlib
import hmac
import logging
import time
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from intelligence.agents.respuesta_inicial_whatsapp_agent import AgenteRespuestaInicialWhatsApp
from n8n_bridge.models import PropertyBotInitialResponse

from .initial_property_config import get_bot_configuration, schedule_state
from .initial_property_detector import (
    extract_property_identity,
    title_is_consistent,
    detect_captacion_intent,
)
from .initial_property_memory import save_initial_episode
from .initial_property_renderer import render_initial_response, render_captacion_response
from .initial_property_validator import validate_property_payload, validate_rendered_response


logger = logging.getLogger(__name__)
BLOCKED_STATUSES = {"vendida", "vendido", "pausada", "pausado", "no disponible"}


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
    return {
        "success": True,
        "action": record.action,
        "reply_text": record.response_text if record.action == "respond_once" else "",
        "reason_code": "DUPLICATE_MESSAGE" if duplicate else record.reason_code,
        "interaction_id": str(record.id),
        "property_code": record.property_code,
        "bot_finished_for_conversation": record.action == "respond_once",
    }


def process_initial_message(payload):
    """Procesa el primer mensaje de un hilo con lógica real one-shot."""
    started = time.monotonic()
    message_id = str(payload.get("message_id") or "").strip()
    text = str(payload.get("text") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    external_id = str(payload.get("external_conversation_id") or "").strip()
    contact_name = str(payload.get("contact_name") or "").strip()

    # Modo shadow_live (opcional, RESPONSE_INTELLIGENCE_SHADOW=1): genera un
    # borrador IA en un hilo daemon sin enviar nada ni alterar esta respuesta.
    if text:
        try:
            from response_intelligence.shadow import spawn_shadow_draft

            spawn_shadow_draft(
                client_message=text,
                thread_id=external_id or phone,
                phone=phone,
            )
        except Exception:  # noqa: BLE001
            pass

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
                    reason_code="CAPTACION_SENT",
                    evidence={"lead_type": "captacion", "intent": "vender"},
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
        episode = save_initial_episode(
            phone, contact_name, text, reply,
            {"lead_type": "captacion", "intent": "vender"},
        )
        if episode and episode.get("id"):
            record.episode_id = episode["id"]
            record.save(update_fields=["episode_id"])
        return _response_from_record(record)

    identity = extract_property_identity(text)
    if not identity["codes"]:
        return _persist_ignore(message_id, thread_id, digest, normalized_phone, text, config, schedule, "NO_PROPERTY_CODE", started, contact_name=contact_name)
    if len(identity["codes"]) != 1:
        return _persist_ignore(message_id, thread_id, digest, normalized_phone, text, config, schedule, "MULTIPLE_PROPERTY_CODES", started, contact_name=contact_name)

    code = identity["codes"][0]
    skill_result = AgenteRespuestaInicialWhatsApp().resolve(code, {"channel": "whatsapp"})
    if not skill_result.success:
        reason = (skill_result.metadata or {}).get("reason_code", "INTERNAL_ERROR")
        return _persist_ignore(message_id, thread_id, digest, normalized_phone, text, config, schedule, reason, started, property_code=code, contact_name=contact_name)

    data = skill_result.data
    data_clean = _json_safe(data)
    # El hint es consistente si coincide con el TÍTULO, la DESCRIPCIÓN, la
    # DIRECCIÓN (map_address) o el CÓDIGO de la propiedad. El cliente suele
    # referirse a la propiedad por su ubicación ("atrás del Real Plaza"), un
    # dato de la descripción o el propio código, no solo por el título.
    hint = identity["title_hint"]
    title_ok = title_is_consistent(hint, data["title"])
    desc_ok = title_is_consistent(hint, data.get("description") or "")
    addr_ok = title_is_consistent(hint, data.get("map_address") or "")
    code_upper = str(data.get("code") or "").upper()
    hint_upper = str(hint).upper()
    code_ok = bool(hint) and (code_upper in hint_upper or hint_upper in code_upper)
    if hint and not (title_ok or desc_ok or addr_ok or code_ok):
        return _persist_ignore(
            message_id, thread_id, digest, normalized_phone, text, config, schedule,
            "TITLE_CODE_MISMATCH", started, property_code=code,
            evidence={
                "title_hint": hint,
                "property_title": data["title"],
                "property_description": data.get("description") or "",
                "map_address": data.get("map_address") or "",
            },
            contact_name=contact_name,
        )
    # Sin restricción de tipo: se responde cualquier tipo de propiedad
    # (casa, departamento, terreno, local comercial, "Otros"/hotel, etc.).
    # Solo se responden propiedades en estado "Disponible" (property_status_name).
    # La visibilidad (is_visible) ya no bloquea: si está disponible, el bot responde.
    status = str(data.get("property_status") or "").lower().strip()
    if status != "disponible":
        return _persist_ignore(message_id, thread_id, digest, normalized_phone, text, config, schedule, "PROPERTY_NOT_PUBLISHABLE", started, property_code=code, contact_name=contact_name)

    valid, reason = validate_property_payload(data)
    if not valid:
        return _persist_ignore(message_id, thread_id, digest, normalized_phone, text, config, schedule, reason, started, property_code=code, evidence=data, contact_name=contact_name)
    reply = render_initial_response(data, config)
    if not validate_rendered_response(reply, data):
        return _persist_ignore(message_id, thread_id, digest, normalized_phone, text, config, schedule, "VALIDATION_FAILED", started, property_code=code, evidence=data, contact_name=contact_name)

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
