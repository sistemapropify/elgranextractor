"""Identidad y contexto secuencial para conversaciones del motor sombra.

El CRM es la fuente de los turnos del lead. Las respuestas humanas no se
inyectan en la conversación alternativa: cada respuesta sombra se apoya solo
en los mensajes del lead y en las respuestas sombra generadas anteriormente.
"""

from __future__ import annotations

import hashlib
import re

from lead_intelligence.conversation_analysis import normalize_text


PROPERTY_CODE_RE = re.compile(r"\bPROP\d{6,9}\b", re.IGNORECASE)


def draft_context(draft) -> dict:
    snapshot = getattr(draft, "prompt_snapshot", None) or {}
    return snapshot.get("context") or {}


def identity_key(*, lead_id=None, thread_id=None, phone=None):
    """Identidad estable de un hilo, incluso para drafts antiguos sin lead_id."""
    if lead_id:
        return ("lead", str(lead_id))
    thread = str(thread_id or "").strip()
    if thread:
        return ("thread", thread)
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    return ("phone", digits[-9:]) if digits else ("unknown", "")


def draft_identity_key(draft):
    context = draft_context(draft)
    return identity_key(
        lead_id=getattr(draft, "source_lead_id", None),
        thread_id=context.get("thread_id"),
        phone=context.get("phone"),
    )


def message_event_key(*, lead_id=None, thread_id=None, phone=None, message, index):
    """Fingerprint de un turno; distingue textos repetidos por posición/fecha."""
    identity = "|".join(identity_key(lead_id=lead_id, thread_id=thread_id, phone=phone))
    timestamp = message.get("timestamp")
    timestamp_value = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp or "")
    source_position = message.get("position", index)
    raw = "|".join(
        [identity, str(source_position), timestamp_value, normalize_text(message.get("text"))]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def draft_event_key(draft) -> str:
    return str(draft_context(draft).get("event_key") or "")


def source_position(draft):
    value = draft_context(draft).get("source_position")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def find_trigger_index(messages, client_message, *, stored_position=None):
    """Ubica el turno exacto. Para legado, el último texto igual es más seguro."""
    if stored_position is not None:
        for index, message in enumerate(messages or []):
            if message.get("sender") == "lead" and message.get("position") == stored_position:
                return index
    target = normalize_text(client_message)
    matches = [
        index
        for index, message in enumerate(messages or [])
        if message.get("sender") == "lead"
        and normalize_text(message.get("text")) == target
    ]
    return matches[-1] if matches else None


def property_code_as_of(messages, target_index=None) -> str:
    """Último código mencionado hasta el turno actual, nunca el primero global."""
    items = list(messages or [])
    if target_index is not None:
        items = items[: target_index + 1]
    for message in reversed(items):
        match = PROPERTY_CODE_RE.search(str(message.get("text") or ""))
        if match:
            return match.group(0).upper()
    return ""


def assign_drafts_to_lead_messages(messages, drafts):
    """Asocia cada draft a un turno sin colapsar mensajes de texto repetido."""
    lead_indices = [i for i, item in enumerate(messages or []) if item.get("sender") == "lead"]
    by_position = {
        messages[i].get("position", i): i
        for i in lead_indices
    }
    assigned = {}
    legacy = []
    for draft in sorted(drafts or [], key=lambda item: (getattr(item, "created_at", None) or 0, getattr(item, "pk", 0) or 0)):
        position = source_position(draft)
        index = by_position.get(position)
        if index is not None and index not in assigned:
            assigned[index] = draft
        else:
            legacy.append(draft)

    # Compatibilidad con drafts históricos: consume ocurrencias en orden para
    # que dos mensajes "Hola" puedan tener dos respuestas diferentes.
    for draft in legacy:
        target = normalize_text(getattr(draft, "client_message", ""))
        index = next(
            (
                i for i in lead_indices
                if i not in assigned and normalize_text(messages[i].get("text")) == target
            ),
            None,
        )
        if index is not None:
            assigned[index] = draft
    return assigned


def shadow_history_before(messages, target_index, drafts):
    """Historia alternativa previa: lead + respuesta sombra, sin agente humano."""
    assigned = assign_drafts_to_lead_messages(messages, drafts)
    history = []
    for index, message in enumerate(messages or []):
        if index >= target_index:
            break
        if message.get("sender") != "lead":
            continue
        history.append({"role": "user", "content": str(message.get("text") or "")})
        draft = assigned.get(index)
        response = str(getattr(draft, "generated_response", "") or "").strip() if draft else ""
        if response:
            history.append({"role": "assistant", "content": response})
    return history[-16:]
