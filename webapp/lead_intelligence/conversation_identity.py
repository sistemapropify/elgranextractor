"""Conversation identity shared by analysis and control, with no LLM imports."""
import hashlib
import json

ANALYSIS_VERSION = 'context-v2'
BOT_SENDER_HASH_VERSION = 'bot-sender-v1'
SEMANTIC_HASH_VERSION = 'lead-analysis-input-v1'


def _contains_bot_sender(raw_history):
    try:
        payload = json.loads(raw_history) if isinstance(raw_history, str) else raw_history
    except (TypeError, ValueError):
        return False
    return isinstance(payload, list) and any(
        isinstance(item, dict) and str(item.get('sender') or '').strip().lower() == 'bot'
        for item in payload
    )


def conversation_hash(raw_history):
    value = raw_history if isinstance(raw_history, str) else json.dumps(raw_history, ensure_ascii=False, sort_keys=True, default=str)
    if _contains_bot_sender(raw_history):
        value += f'\nparser:{BOT_SENDER_HASH_VERSION}'
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def analysis_input_hash(messages):
    """Hash only messages that can change the contextual assessment.

    Lead messages can change commercial qualification or visit intent. The
    first contiguous agent response block can change first-response quality.
    Later agent and bot messages cannot change those decisions because they
    occur outside the first-response evaluation window.
    """
    selected = []
    lead_seen = False
    first_response_open = False
    first_response_closed = False
    for message in messages or []:
        sender = str(message.get("sender") or "").strip().lower()
        if sender == "lead":
            selected.append(message)
            lead_seen = True
            if first_response_open:
                first_response_open = False
                first_response_closed = True
            continue
        if sender == "agent" and lead_seen and not first_response_closed:
            selected.append(message)
            first_response_open = True

    canonical = []
    for message in selected:
        timestamp = message.get("timestamp")
        if hasattr(timestamp, "isoformat"):
            timestamp = timestamp.isoformat()
        canonical.append(
            {
                "sender": str(message.get("sender") or "").strip().lower(),
                "source_sender": str(
                    message.get("source_sender")
                    or message.get("sender")
                    or ""
                ).strip().lower(),
                "timestamp": str(timestamp or ""),
                "text": str(message.get("text") or ""),
            }
        )
    payload = json.dumps(
        {"version": SEMANTIC_HASH_VERSION, "messages": canonical},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
