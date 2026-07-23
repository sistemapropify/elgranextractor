"""Auditoría intensiva de cada interacción durante la fase de estabilización."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

from .redaction import redact_text, sanitize_payload

logger = logging.getLogger(__name__)


def audit_enabled() -> bool:
    return bool(getattr(settings, 'LEARNING_AI_AUDIT_ALL', True))


def audit_interaction(
    *,
    query: str,
    response: str,
    orchestration_mode: str,
    result_count: int | None,
    grounded: bool | None,
    execution_summary: list[dict[str, Any]],
    result_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    signals = []
    if result_count is None:
        signals.append('MISSING_RESULT_COUNT')
    if grounded is not True:
        signals.append('GROUNDING_NOT_CONFIRMED')
    if any(
        agent.get('success') is False
        or any(step.get('success') is False for step in agent.get('steps') or [])
        for agent in execution_summary
    ):
        signals.append('INTERNAL_STEP_FAILED')
    if any(
        step.get('item_count', 0) == 0 and step.get('success') is True
        for step in execution_summary
        if step.get('skill_name')
    ):
        signals.append('SUCCESS_WITH_ZERO_ITEMS')

    base = {
        'audit_verdict': 'review' if signals else 'pass',
        'audit_confidence': 1.0 if signals else 0.8,
        'audit_summary': (
            'Se detectaron señales deterministas que requieren revisión.'
            if signals else 'No se detectaron inconsistencias deterministas.'
        ),
        'audit_signals': signals,
    }
    if not audit_enabled():
        return base

    prompt_payload = sanitize_payload({
        'orchestration_mode': orchestration_mode,
        'result_count': result_count,
        'grounded': grounded,
        'steps': execution_summary,
        'result_evidence': result_evidence or [],
    })
    prompt = f"""Audita esta ejecución de un asistente inmobiliario.
Busca errores silenciosos: datos inventados, conteos inconsistentes, filtros
omitidos, pasos fallidos marcados como éxito, respuesta no fundamentada o
resultado vacío causado por un error técnico.

Consulta redactada: {redact_text(query, 400)}
Respuesta redactada: {redact_text(response, 1200)}
Ejecución y evidencia recuperada: {json.dumps(prompt_payload, ensure_ascii=True, default=str)}
Señales deterministas: {json.dumps(signals)}

Solo usa DATA_INVENTED cuando un dato concreto de la respuesta contradiga la
evidencia recuperada. Si no hay evidencia suficiente para comparar, usa
INSUFFICIENT_GROUNDING_EVIDENCE y verdict review, nunca DATA_INVENTED.

Responde SOLO JSON:
{{
  "verdict": "pass|review|fail",
  "confidence": 0.0,
  "summary": "explicación breve",
  "signals": ["CODIGO"]
}}"""
    try:
        from ..services.llm import LLMService

        success, _, api_response = LLMService._call_deepseek_api(
            messages=[{'role': 'user', 'content': prompt}],
            system_prompt='Eres un auditor técnico estricto. No inventes evidencia.',
            caller_app='learning_auditor',
            endpoint='audit_interaction',
        )
        if success and api_response:
            content = api_response.get('content', '')
            start = content.find('{')
            end = content.rfind('}')
            if start >= 0 and end > start:
                parsed = json.loads(content[start:end + 1])
                verdict = parsed.get('verdict', 'review')
                combined_signals = list(dict.fromkeys(
                    signals + list(parsed.get('signals') or [])
                ))
                if signals and verdict == 'pass':
                    verdict = 'review'
                return {
                    'audit_verdict': verdict,
                    'audit_confidence': float(parsed.get('confidence', 0.5)),
                    'audit_summary': redact_text(parsed.get('summary'), 300),
                    'audit_signals': combined_signals,
                }
    except Exception as exc:
        logger.warning("Auditoría IA no disponible: %s", exc)

    base['audit_verdict'] = 'review'
    base['audit_signals'] = list(dict.fromkeys(signals + ['AI_AUDIT_UNAVAILABLE']))
    return base
