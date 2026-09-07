"""Conversation identity shared by analysis and control, with no LLM imports."""
import hashlib
import json

ANALYSIS_VERSION = 'context-v2'
BOT_SENDER_HASH_VERSION = 'bot-sender-v1'


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
