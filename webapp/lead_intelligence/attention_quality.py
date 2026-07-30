"""Deterministic conversation-service metrics derived from chat_history."""

from __future__ import annotations

import math
import re
from statistics import median

from .conversation_analysis import normalize_text


MEDIA_REQUEST_PATTERN = re.compile(
    r"\b(?:foto|fotos|imagen|imagenes|video|videos|plano|planos|"
    r"ambiente|ambientes|ver\s+(?:el|la|los|las))\b"
)
MEDIA_DELIVERY_HINT_PATTERN = re.compile(
    r"\b(?:aqui|adjunt|envio|enviando|mando|mandando|comparto|"
    r"estos?\s+son|estas?\s+son|mira|claro)\b"
)
REQUEST_SIGNAL_GROUPS = (
    (
        ("precio", "costo", "valor", "monto"),
        ("precio", "costo", "cuanto", "valor", "monto", "dolares", "soles"),
    ),
    (
        ("ubicacion", "direccion", "lugar", "zona"),
        ("ubicacion", "direccion", "donde", "lugar", "zona", "distrito"),
    ),
    (
        ("caracteristica", "adicional", "detalle"),
        (
            "caracteristica",
            "detalle",
            "habitacion",
            "dormitorio",
            "cochera",
            "ascensor",
            "piso",
            "area",
            "metros",
            "m2",
        ),
    ),
    (
        ("financiamiento", "credito", "banco"),
        ("financiamiento", "credito", "banco", "cuotas"),
    ),
)
REQUEST_ITEM_STOPWORDS = {
    "de",
    "del",
    "el",
    "en",
    "general",
    "informacion",
    "la",
    "las",
    "los",
    "mas",
    "sobre",
    "un",
    "una",
    "y",
}


def response_wait_seconds(messages):
    """Measure each lead turn until the next agent response.

    Consecutive lead messages form one turn. The wait starts at the last
    message in that block, which represents the moment the customer finished
    adding context.
    """

    waits = []
    waiting_since = None
    for message in messages:
        if message["sender"] == "lead":
            waiting_since = message["timestamp"]
            continue
        if waiting_since is None:
            continue
        seconds = int((message["timestamp"] - waiting_since).total_seconds())
        if seconds >= 0:
            waits.append(seconds)
        waiting_since = None
    return waits


def first_exchange(messages):
    """Return the initial lead block and the first consecutive agent block."""

    initial_lead = []
    first_agent = []
    agent_started = False
    for message in messages:
        if not agent_started:
            if message["sender"] == "lead":
                initial_lead.append(message)
            elif initial_lead:
                agent_started = True
                first_agent.append(message)
            continue
        if message["sender"] == "agent":
            first_agent.append(message)
        else:
            break
    return initial_lead, first_agent


def first_response_text(messages):
    _, agent_block = first_exchange(messages)
    return "\n".join(message["text"] for message in agent_block).strip()


def first_response_indices(messages):
    """Return sorted transcript indexes belonging to the first agent block."""

    indexes = []
    lead_seen = False
    response_started = False
    for index, message in enumerate(messages):
        if not response_started:
            if message["sender"] == "lead":
                lead_seen = True
            elif lead_seen:
                response_started = True
                indexes.append(index)
            continue
        if message["sender"] != "agent":
            break
        indexes.append(index)
    return set(indexes)


def validate_initial_request_items(messages, items):
    """Reject request details the model inferred but the lead never stated."""

    initial_lead, _ = first_exchange(messages)
    initial_text = normalize_text(
        " ".join(message["text"] for message in initial_lead)
    )
    initial_tokens = set(initial_text.split())
    grounded = []
    unsupported = []
    for raw_item in items or []:
        item = str(raw_item).strip()
        normalized_item = normalize_text(item)
        supported = None
        for item_signals, request_signals in REQUEST_SIGNAL_GROUPS:
            if any(signal in normalized_item for signal in item_signals):
                supported = any(signal in initial_text for signal in request_signals)
                break
        if supported is None:
            meaningful_tokens = {
                token
                for token in normalized_item.split()
                if len(token) >= 3 and token not in REQUEST_ITEM_STOPWORDS
            }
            supported = bool(meaningful_tokens & initial_tokens)
        (grounded if supported else unsupported).append(item)
    return grounded, unsupported


def possible_missing_media(messages):
    """Detect when text alone cannot prove whether requested media was sent.

    ``lead.chat_history`` may omit Chatwoot attachment-only messages. This
    function is intentionally conservative: it only raises a risk when the
    initial lead block requests visual material and the first agent block
    reads like a delivery or affirmative response without an attachment
    marker in the stored history.
    """

    lead_block, agent_block = first_exchange(messages)
    if not lead_block or not agent_block:
        return False
    lead_text = normalize_text(
        " ".join(message["text"] for message in lead_block)
    )
    agent_text = normalize_text(
        " ".join(message["text"] for message in agent_block)
    )
    stored_attachment = any(
        message["text"].startswith("[") and message["text"].endswith("]")
        for message in agent_block
    )
    return bool(
        MEDIA_REQUEST_PATTERN.search(lead_text)
        and MEDIA_DELIVERY_HINT_PATTERN.search(agent_text)
        and not stored_attachment
    )


def template_signature(text):
    """Create a conservative signature for repeated first-response templates."""

    normalized = normalize_text(text)
    normalized = re.sub(r"https?://\S+|www\.\S+", " <url> ", normalized)
    normalized = re.sub(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", " <email> ", normalized)
    normalized = re.sub(r"\b\d+(?:[.,]\d+)*\b", " <n> ", normalized)
    normalized = re.sub(r"[^a-z0-9<>]+", " ", normalized)
    normalized = " ".join(normalized.split())
    return normalized[:1200] if len(normalized) >= 20 else ""


def percentile(values, percent):
    values = sorted(float(value) for value in values if value is not None)
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * percent / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    fraction = position - lower
    return values[lower] + (values[upper] - values[lower]) * fraction


def median_or_none(values):
    values = [float(value) for value in values if value is not None]
    return median(values) if values else None


def average_or_none(values):
    values = [float(value) for value in values if value is not None]
    return sum(values) / len(values) if values else None


def duration_label(seconds):
    if seconds is None:
        return "—"
    seconds = max(0, int(round(float(seconds))))
    if seconds < 60:
        return f"{seconds} s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours, remainder = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} h {remainder:02d} min"
    days, remainder_hours = divmod(hours, 24)
    return f"{days} d {remainder_hours} h"
