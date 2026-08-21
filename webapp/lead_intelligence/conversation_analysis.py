"""Deterministic analysis of CRM lead conversations stored as JSON."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timezone as datetime_timezone
from zoneinfo import ZoneInfo

from django.utils.dateparse import parse_datetime


LIMA_TIMEZONE = ZoneInfo("America/Lima")
SENDER_ALIASES = {"lead": "lead", "agent": "agent", "bot": "agent"}
RECOGNIZED_SENDERS = set(SENDER_ALIASES)
NEGATIVE_INTEREST_PATTERNS = (
    r"\bno\s+(?:me\s+)?interesa\b",
    r"\b(?:numero|número|contacto)\s+equivocado\b",
    r"\bse\s+equivoco\b",
)
INTEREST_PATTERNS = (
    r"\bme\s+interesa\b",
    r"\b(?:precio|costo|cuanto\s+(?:cuesta|vale))\b",
    r"\b(?:ubicacion|direccion|maps|mapa)\b",
    r"\b(?:foto|fotos|video|videos)\b",
    r"\b(?:area|metros?|m2|caracteristicas?)\b",
    r"\bdisponib(?:le|ilidad)\b",
    r"\b(?:financiamiento|credito|cuota|inicial)\b",
    r"\b(?:documentos?|titulo|parametros?)\b",
    r"\b(?:comprar|vivienda|proyecto)\b",
    r"\b(?:negociar|separar|reservar)\b",
    r"\b(?:visitar|visita|ver(?:l[oa])?|agendar|coordinar|reunir|reunion)\b",
)
VISIT_INTENT_PATTERNS = (
    r"\b(?:quiero|quisiera|deseo|prefiero|me\s+gustaria|podemos|puedo|podria)\b.{0,60}\b(?:visitar(?:l[oa])?|visita|ver(?:l[oa])?|conocer(?:l[oa])?|agendar|coordinar|programar)\b",
    r"\b(?:agendemos|coordinemos|programemos)\b.{0,40}\b(?:visita|reunion|ver)?\b",
    r"\b(?:cuando|que\s+dia|que\s+hora)\b.{0,50}\b(?:puedo|podemos|podria)\b.{0,30}\b(?:visitar(?:l[oa])?|ver(?:l[oa])?|conocer(?:l[oa])?)\b",
)
VISIT_PROPOSAL_PATTERNS = (
    r"\b(?:coordinar|agendar|programar)\b.{0,50}\b(?:visita|reunion|ver(?:l[oa])?)\b",
    r"\b(?:quiere|quisiera|desea|puede|podemos)\b.{0,50}\b(?:visitar(?:l[oa])?|visita|ver(?:l[oa])?|conocer(?:l[oa])?)\b",
)
AFFIRMATIVE_PATTERNS = (
    r"^(?:si|sí|claro|ok|okay|de\s+acuerdo|perfecto|correcto|esta\s+bien|me\s+parece)(?:\b|[,.!])",
)
ATTACHMENT_KEYS = {
    "attachment",
    "attachments",
    "file",
    "files",
    "image",
    "images",
    "media",
    "url",
}
ATTACHMENT_MARKERS = {
    "adjunto",
    "archivo",
    "documento",
    "foto",
    "imagen",
    "video",
}


def normalize_text(value) -> str:
    """Normalize case, accents and whitespace for deterministic matching."""
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.split())


def _message_content(message: dict) -> str:
    for key in ("text", "content", "body", "caption"):
        value = message.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    for key in ATTACHMENT_KEYS:
        value = message.get(key)
        if value:
            return f"[{key}]"
    return ""


def _has_useful_content(content: str) -> bool:
    normalized = normalize_text(content)
    if not normalized:
        return False
    if re.search(r"https?://|www\.", normalized):
        return True
    stripped_marker = normalized.strip("[](){}<> ")
    return bool(stripped_marker) and (
        any(marker in stripped_marker for marker in ATTACHMENT_MARKERS)
        or bool(re.search(r"[\w\d]", normalized, flags=re.UNICODE))
    )


def _timestamp(value) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = parse_datetime(value.strip())
    else:
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=datetime_timezone.utc)
    return parsed.astimezone(datetime_timezone.utc)


def has_interest(text: str) -> bool:
    """Return whether a lead message contains a concrete commercial signal."""
    normalized = normalize_text(text)
    if any(re.search(pattern, normalized) for pattern in NEGATIVE_INTEREST_PATTERNS):
        return False
    return any(re.search(pattern, normalized) for pattern in INTEREST_PATTERNS)


def has_visit_intent(text: str) -> bool:
    normalized = normalize_text(text)
    if any(re.search(pattern, normalized) for pattern in NEGATIVE_INTEREST_PATTERNS):
        return False
    return any(re.search(pattern, normalized) for pattern in VISIT_INTENT_PATTERNS)


def _has_visit_proposal(text: str) -> bool:
    normalized = normalize_text(text)
    return any(re.search(pattern, normalized) for pattern in VISIT_PROPOSAL_PATTERNS)


def _is_affirmative(text: str) -> bool:
    normalized = normalize_text(text)
    return any(re.search(pattern, normalized) for pattern in AFFIRMATIVE_PATTERNS)


def lima_date(value: datetime | None) -> date | None:
    if value is None:
        return None
    normalized = _timestamp(value)
    return normalized.astimezone(LIMA_TIMEZONE).date() if normalized else None


def milestone_within_days(
    cohort_date: date, reached_at: datetime | None, max_days: int
) -> bool:
    """Check a milestone window using calendar dates in America/Lima."""
    reached_date = lima_date(reached_at)
    if reached_date is None:
        return False
    elapsed_days = (reached_date - cohort_date).days
    return 0 <= elapsed_days <= max_days


def analyze_chat_history(raw_history) -> dict:
    """Analyze one ``lead.chat_history`` value without raising on bad data."""
    is_null = raw_history is None
    valid_json = True
    if is_null:
        payload = []
    elif isinstance(raw_history, str):
        if not raw_history.strip():
            payload = []
        else:
            try:
                payload = json.loads(raw_history)
            except (TypeError, ValueError, json.JSONDecodeError):
                payload = []
                valid_json = False
    elif isinstance(raw_history, list):
        payload = raw_history
    else:
        payload = []
        valid_json = False

    if valid_json and not isinstance(payload, list):
        payload = []
        valid_json = False

    unknown_senders = 0
    messages_without_valid_timestamp = 0
    raw_useful_message_count = 0
    messages = []
    for position, item in enumerate(payload):
        if not isinstance(item, dict):
            continue
        content = _message_content(item)
        if not _has_useful_content(content):
            continue
        raw_useful_message_count += 1
        sender = normalize_text(item.get("sender"))
        if sender not in RECOGNIZED_SENDERS:
            unknown_senders += 1
            continue
        sender = SENDER_ALIASES[sender]
        timestamp = _timestamp(item.get("timestamp"))
        if timestamp is None:
            messages_without_valid_timestamp += 1
            continue
        messages.append(
            {
                "sender": sender,
                "text": content,
                "timestamp": timestamp,
                "position": position,
            }
        )

    # La ingestión externa (Chatwoot/n8n) a veces graba el mismo mensaje dos
    # veces en chat_history (mismo emisor, texto y timestamp). Se deduplican
    # para que la cronología de los leads y las métricas no cuenten duplicados.
    seen = set()
    deduped = []
    for item in messages:
        key = (item["sender"], item["text"], item["timestamp"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    messages = deduped

    messages.sort(key=lambda item: (item["timestamp"], item["position"]))

    lead_messages = [item for item in messages if item["sender"] == "lead"]
    agent_messages = [item for item in messages if item["sender"] == "agent"]
    first_lead_at = lead_messages[0]["timestamp"] if lead_messages else None

    first_agent_response_at = None
    bidirectional_at = None
    qualified_at = None
    visit_intent_at = None
    interest_at = None
    agent_replied = False
    lead_seen = False
    pending_visit_offer = False

    for message in messages:
        if message["sender"] == "lead":
            lead_seen = True
            if has_interest(message["text"]) and interest_at is None:
                interest_at = message["timestamp"]
            explicit_visit_intent = has_visit_intent(message["text"])
            accepted_visit_offer = pending_visit_offer and _is_affirmative(
                message["text"]
            )
            if (
                explicit_visit_intent or accepted_visit_offer
            ) and visit_intent_at is None:
                visit_intent_at = message["timestamp"]
            pending_visit_offer = False
            if agent_replied and bidirectional_at is None:
                bidirectional_at = message["timestamp"]
            if bidirectional_at is not None and interest_at is not None:
                candidate = max(bidirectional_at, interest_at)
                if qualified_at is None or candidate < qualified_at:
                    qualified_at = candidate
        elif lead_seen:
            if first_agent_response_at is None:
                first_agent_response_at = message["timestamp"]
            agent_replied = True
            pending_visit_offer = _has_visit_proposal(message["text"])

    last_message = messages[-1] if messages else None
    last_lead_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if messages[index]["sender"] == "lead"
        ),
        None,
    )
    unattended = last_lead_index is not None and not any(
        message["sender"] == "agent" for message in messages[last_lead_index + 1 :]
    )
    first_response_seconds = None
    if first_lead_at is not None and first_agent_response_at is not None:
        first_response_seconds = int(
            (first_agent_response_at - first_lead_at).total_seconds()
        )

    return {
        "valid_json": valid_json,
        "is_null": is_null,
        "empty_history": not is_null and valid_json and len(payload) == 0,
        "raw_useful_message_count": raw_useful_message_count,
        "messages_without_valid_timestamp": messages_without_valid_timestamp,
        "unknown_senders": unknown_senders,
        "total_messages": len(messages),
        "lead_messages": len(lead_messages),
        "agent_messages": len(agent_messages),
        "first_lead_at": first_lead_at,
        "first_agent_response_at": first_agent_response_at,
        "first_response_seconds": first_response_seconds,
        "contacted": first_agent_response_at is not None,
        "contacted_at": first_agent_response_at,
        "bidirectional": bidirectional_at is not None,
        "bidirectional_at": bidirectional_at,
        "has_interest": interest_at is not None,
        "interest_at": interest_at,
        "qualified": qualified_at is not None,
        "qualified_at": qualified_at,
        "visit_intent": visit_intent_at is not None,
        "visit_intent_at": visit_intent_at,
        "unattended": unattended,
        "last_message_at": last_message["timestamp"] if last_message else None,
        "last_sender": last_message["sender"] if last_message else None,
        "messages": messages,
    }
