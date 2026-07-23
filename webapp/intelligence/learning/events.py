"""API tolerante a fallos para crear trazas y eventos de PIL."""

import logging
import os
import uuid
from typing import Any, Dict, Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from ..models import SystemEvent, SystemTrace
from .redaction import normalized_query_hash, redact_text, sanitize_payload

logger = logging.getLogger(__name__)


def telemetry_enabled() -> bool:
    return bool(getattr(settings, 'LEARNING_TELEMETRY_ENABLED', True))


def start_trace(
    *,
    query: str,
    conversation=None,
    request_kind: str = 'unknown',
    app_id: str = '',
    trace_id: Optional[str] = None,
) -> Optional[SystemTrace]:
    if not telemetry_enabled():
        return None
    try:
        trace = SystemTrace.objects.create(
            trace_id=trace_id or uuid.uuid4().hex,
            conversation=conversation,
            request_kind=request_kind or 'unknown',
            normalized_query_hash=normalized_query_hash(query),
            query_redacted=redact_text(query),
            code_version=os.environ.get('BUILD_VERSION', 'unknown')[:64],
            config_version=os.environ.get('PIL_CONFIG_VERSION', 'unknown')[:64],
            embedding_version=os.environ.get('PIL_EMBEDDING_VERSION', 'e5-small-384')[:64],
            metadata=sanitize_payload({'app_id': app_id}),
        )
        emit_event(
            trace,
            'trace.started',
            'chat_processor',
            payload={'app_id': app_id, 'request_kind': request_kind},
        )
        return trace
    except Exception as exc:
        logger.warning("No se pudo iniciar SystemTrace: %s", exc)
        return None


def emit_event(
    trace: Optional[SystemTrace],
    event_type: str,
    component: str,
    *,
    outcome: str = 'info',
    error_code: str = '',
    payload: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[int] = None,
) -> Optional[SystemEvent]:
    if trace is None or not telemetry_enabled():
        return None
    try:
        with transaction.atomic():
            locked = SystemTrace.objects.select_for_update().get(pk=trace.pk)
            current = locked.events.aggregate(max_seq=Max('sequence'))['max_seq'] or 0
            return SystemEvent.objects.create(
                trace=locked,
                sequence=current + 1,
                event_type=event_type[:80],
                component=component[:100],
                outcome=outcome[:30],
                error_code=error_code[:80],
                payload=sanitize_payload(payload),
                duration_ms=duration_ms,
            )
    except Exception as exc:
        logger.warning("No se pudo emitir SystemEvent: %s", exc)
        return None


def complete_trace(
    trace: Optional[SystemTrace],
    *,
    success: bool,
    orchestration_mode: str = '',
    result_count: Optional[int] = None,
    grounded: Optional[bool] = None,
    latency_ms: Optional[float] = None,
    error: Optional[Exception | str] = None,
    review_required: bool = False,
) -> None:
    if trace is None or not telemetry_enabled():
        return
    try:
        status = 'completed' if success else 'failed'
        if success and result_count == 0:
            status = 'completed_empty'
        if success and 'fallback' in (orchestration_mode or '').casefold():
            status = 'completed_degraded'
        if success and review_required:
            status = 'needs_review'
        error_preview = redact_text(error, 250) if error else ''
        trace.status = status
        trace.technical_success = success
        trace.orchestration_mode = (orchestration_mode or '')[:50]
        trace.result_count = result_count
        trace.grounded = grounded
        trace.latency_ms = int(latency_ms) if latency_ms is not None else None
        trace.completed_at = timezone.now()
        trace.save(update_fields=[
            'status', 'technical_success', 'orchestration_mode', 'result_count',
            'grounded', 'latency_ms', 'completed_at',
        ])
        emit_event(
            trace,
            'trace.completed',
            'chat_processor',
            outcome='success' if success else 'error',
            error_code='UNHANDLED_ERROR' if error else '',
            payload={
                'status': status,
                'orchestration_mode': orchestration_mode,
                'result_count': result_count,
                'grounded': grounded,
                'error_type': type(error).__name__ if isinstance(error, Exception) else '',
                'error_preview': error_preview,
            },
            duration_ms=trace.latency_ms,
        )
    except Exception as exc:
        logger.warning("No se pudo completar SystemTrace: %s", exc)
