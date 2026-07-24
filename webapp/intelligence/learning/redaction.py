"""Redacción defensiva para telemetría de aprendizaje."""

import re
from hashlib import sha256
from typing import Any, Dict


MAX_TEXT_LENGTH = 500
ALLOWED_PAYLOAD_KEYS = {
    'app_id', 'orchestration_mode', 'skill_name', 'agent_names',
    'result_count', 'grounded', 'fallback_used', 'status',
    'error_type', 'error_preview', 'request_kind',
    'step_count', 'steps', 'agent_name', 'skill_name', 'success',
    'iterations', 'item_count', 'filter_count', 'audit_verdict',
    'audit_confidence', 'audit_summary', 'audit_signals',
    'response_claimed_count', 'search_plan_hash',
    'result_evidence',
    'confidence', 'verdict', 'signals', 'metrics', 'critique_retries',
    'mode', 'latency_ms', 'disagrees_with_deterministic',
    'authority_applied', 'action', 'reason', 'retries_used',
    'judge_status', 'judge_verdict', 'judge_confidence', 'judge_attempts',
}

_PATTERNS = [
    (re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}'), '[EMAIL]'),
    (re.compile(r'(?<!\d)(?:\+?51[\s-]?)?9\d{8}(?!\d)'), '[PHONE]'),
    (re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+'), r'\1[TOKEN]'),
    (re.compile(r'(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+'), r'\1=[REDACTED]'),
]


def redact_text(value: Any, max_length: int = MAX_TEXT_LENGTH) -> str:
    text = str(value or '')
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:max_length]


def normalized_query_hash(value: Any) -> str:
    normalized = ' '.join(str(value or '').casefold().split())
    return sha256(normalized.encode('utf-8')).hexdigest()


def sanitize_payload(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    safe = {}
    for key, value in (payload or {}).items():
        if key not in ALLOWED_PAYLOAD_KEYS:
            continue
        if isinstance(value, str):
            safe[key] = redact_text(value, 250)
        elif isinstance(value, (bool, int, float)) or value is None:
            safe[key] = value
        elif isinstance(value, list):
            safe[key] = [_sanitize_nested(item) for item in value[:50]]
        elif isinstance(value, dict):
            safe[key] = {
                str(k)[:50]: _sanitize_nested(v)
                for k, v in list(value.items())[:30]
            }
    return safe


def _sanitize_nested(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value, 150)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, dict):
        return {
            str(key)[:50]: _sanitize_nested(item)
            for key, item in list(value.items())[:20]
        }
    if isinstance(value, list):
        return [_sanitize_nested(item) for item in value[:20]]
    return redact_text(value, 100)
