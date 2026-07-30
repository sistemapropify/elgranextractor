"""Contextual LLM classification with strict evidence validation."""

from __future__ import annotations

import hashlib
import json

from intelligence.services.llm import LLMService


ANALYSIS_VERSION = "context-v2"
VALID_DECISIONS = {"confirmed", "not_confirmed", "ambiguous"}
VALID_ATTENTION_DECISIONS = {
    "adequate",
    "partial",
    "inadequate",
    "not_applicable",
    "ambiguous",
}


def conversation_hash(raw_history) -> str:
    if isinstance(raw_history, str):
        value = raw_history
    else:
        value = json.dumps(raw_history, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _confidence(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _decision(value) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in VALID_DECISIONS else "ambiguous"


def _attention_decision(value) -> str:
    normalized = str(value or "").strip().lower()
    return (
        normalized
        if normalized in VALID_ATTENTION_DECISIONS
        else "ambiguous"
    )


def _optional_score(value):
    if value is None or value == "":
        return None
    return _confidence(value)


def _string_list(value):
    if not isinstance(value, list):
        return []
    return [
        str(item).strip()[:300]
        for item in value
        if str(item).strip()
    ][:20]


def _validated_evidence(
    indices,
    messages,
    required_sender="lead",
    allowed_indices=None,
):
    evidence = []
    if not isinstance(indices, list):
        return evidence
    for raw_index in indices:
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if index < 0 or index >= len(messages):
            continue
        if allowed_indices is not None and index not in allowed_indices:
            continue
        message = messages[index]
        if message["sender"] != required_sender:
            continue
        evidence.append(
            {
                "message_index": index,
                "sender": required_sender,
                "timestamp": message["timestamp"].isoformat(),
                "text": message["text"],
            }
        )
    return evidence


def _first_response_agent_indices(messages):
    indices = []
    lead_seen = False
    response_started = False
    for index, message in enumerate(messages):
        if not response_started:
            if message["sender"] == "lead":
                lead_seen = True
            elif lead_seen:
                response_started = True
                indices.append(index)
            continue
        if message["sender"] != "agent":
            break
        indices.append(index)
    return set(indices)


def analyze_conversation_context(messages: list[dict]) -> dict:
    transcript = [
        {
            "message_index": index,
            "sender": message["sender"],
            "timestamp": message["timestamp"].isoformat(),
            "text": message["text"],
        }
        for index, message in enumerate(messages)
    ]
    instructions = {
        "task": "Evalúa la conversación completa, incluyendo quién propone, respuestas, condiciones, rechazos y cambios posteriores.",
        "qualified": "Confirmado solo si el lead muestra interés comercial concreto. Una respuesta social aislada no basta.",
        "visit_intent": (
            "Confirmado solo si el lead solicita/proponer visitar, acepta claramente una propuesta del agente, "
            "ofrece disponibilidad o acuerda fecha/hora. Pedir ubicación, precio o características no basta. "
            "Una propuesta exclusiva del agente no es intención del lead."
        ),
        "evidence": "Devuelve únicamente índices de mensajes escritos por el lead que prueban cada decisión.",
        "uncertainty": "Si la evidencia no permite afirmar la decisión, usa ambiguous o not_confirmed; nunca supongas.",
        "attention_quality": (
            "Evalúa también la primera atención. La solicitud inicial comprende "
            "todos los mensajes consecutivos del lead anteriores a la primera "
            "respuesta. La primera respuesta comprende todos los mensajes "
            "consecutivos del agente hasta que el lead vuelve a escribir. "
            "Determina si responde directa y completamente lo pedido. No "
            "penalices una plantilla por repetirse: penaliza solamente si es "
            "genérica, evade, contradice o deja solicitudes sin responder."
        ),
        "explicit_request_rule": (
            "Extrae únicamente solicitudes o preguntas expresadas de forma "
            "explícita por el lead en su bloque inicial. Frases genéricas como "
            "'más info', 'información' o el mensaje automático de un anuncio "
            "NO autorizan a inventar que pidió precio, ubicación, área, "
            "financiamiento ni características. Si la petición es genérica, "
            "una respuesta pertinente que aporte información del inmueble o "
            "haga una pregunta razonable para precisar la necesidad puede ser "
            "adecuada; evalúa lo que realmente se escribió."
        ),
        "first_response_scope": (
            "answered_request_items y unanswered_request_items describen solo "
            "la cobertura del PRIMER bloque de respuesta. Mensajes posteriores "
            "pueden resolver esas dudas, pero no cambian retroactivamente la "
            "calidad de la primera respuesta. No presentes esas omisiones como "
            "solicitudes pendientes al cierre de toda la conversación."
        ),
        "attention_scores": (
            "relevance mide si habla de lo solicitado; coverage qué proporción "
            "de solicitudes concretas responde; directness si responde sin "
            "desviar la conversación; personalization si adapta la respuesta "
            "a las necesidades expresadas, no solo si usa el nombre."
        ),
        "conversation": transcript,
    }
    schema = {
        "qualified_status": "Uno de: confirmed, not_confirmed, ambiguous.",
        "qualified_confidence": (
            "Confianza en que qualified_status es correcto, entre 0 y 1. "
            "También debe ser alta cuando not_confirmed está claramente sustentado."
        ),
        "qualified_evidence_indices": "Lista de message_index escritos por el lead que sustentan la calificación.",
        "visit_intent_status": "Uno de: confirmed, not_confirmed, ambiguous.",
        "visit_intent_confidence": (
            "Confianza en que visit_intent_status es correcto, entre 0 y 1. "
            "No es probabilidad positiva: si claramente no hay intención, usa not_confirmed con confianza alta."
        ),
        "visit_intent_evidence_indices": "Lista de message_index escritos por el lead que demuestran intención real de visita.",
        "reason": "Explicación breve que contraste lo dicho por el lead con las propuestas del agente.",
        "first_response_status": (
            "Uno de: adequate, partial, inadequate, not_applicable, ambiguous. "
            "Adequate exige respuesta pertinente y suficiente; partial responde "
            "solo una parte; inadequate ignora, evade o contradice; "
            "not_applicable si no existe solicitud evaluable o respuesta."
        ),
        "first_response_confidence": "Confianza entre 0 y 1 en first_response_status.",
        "relevance_score": "Puntuación entre 0 y 1.",
        "coverage_score": "Puntuación entre 0 y 1.",
        "directness_score": "Puntuación entre 0 y 1.",
        "personalization_score": "Puntuación entre 0 y 1.",
        "lead_request_items": (
            "Lista breve solo de solicitudes explícitas del bloque inicial del "
            "lead; no descompongas 'más info' en detalles que no mencionó."
        ),
        "answered_request_items": (
            "Solicitudes iniciales explícitas cubiertas por el primer bloque "
            "del agente."
        ),
        "unanswered_request_items": (
            "Solicitudes iniciales explícitas no cubiertas suficientemente por "
            "el primer bloque del agente; no significa pendiente al cierre."
        ),
        "first_response_agent_indices": "Índices message_index del primer bloque de respuesta del agente.",
        "attention_reason": "Explicación breve y verificable de la calidad de la primera respuesta.",
    }
    extracted = None
    message = ""
    for _attempt in range(3):
        success, message, extracted = LLMService.extract_structured_data(
            text=json.dumps(instructions, ensure_ascii=False),
            schema=schema,
        )
        if success and extracted:
            break
    if not extracted:
        raise RuntimeError(message or "No se obtuvo evaluación contextual")

    qualified_status = _decision(extracted.get("qualified_status"))
    visit_status = _decision(extracted.get("visit_intent_status"))
    qualified_evidence = _validated_evidence(
        extracted.get("qualified_evidence_indices"), messages
    )
    visit_evidence = _validated_evidence(
        extracted.get("visit_intent_evidence_indices"), messages
    )
    first_response_status = _attention_decision(
        extracted.get("first_response_status")
    )
    first_response_evidence = _validated_evidence(
        extracted.get("first_response_agent_indices"),
        messages,
        required_sender="agent",
        allowed_indices=_first_response_agent_indices(messages),
    )
    if qualified_status == "confirmed" and not qualified_evidence:
        qualified_status = "ambiguous"
    if visit_status == "confirmed" and not visit_evidence:
        visit_status = "ambiguous"
    if (
        first_response_status
        in {"adequate", "partial", "inadequate"}
        and not first_response_evidence
    ):
        first_response_status = "ambiguous"

    return {
        "qualified_status": qualified_status,
        "qualified_confidence": _confidence(extracted.get("qualified_confidence")),
        "qualified_evidence": qualified_evidence,
        "visit_intent_status": visit_status,
        "visit_intent_confidence": _confidence(
            extracted.get("visit_intent_confidence")
        ),
        "visit_intent_evidence": visit_evidence,
        "reason": str(extracted.get("reason") or "").strip(),
        "first_response_status": first_response_status,
        "first_response_confidence": _confidence(
            extracted.get("first_response_confidence")
        ),
        "relevance_score": _optional_score(
            extracted.get("relevance_score")
        ),
        "coverage_score": _optional_score(extracted.get("coverage_score")),
        "directness_score": _optional_score(
            extracted.get("directness_score")
        ),
        "personalization_score": _optional_score(
            extracted.get("personalization_score")
        ),
        "lead_request_items": _string_list(
            extracted.get("lead_request_items")
        ),
        "answered_request_items": _string_list(
            extracted.get("answered_request_items")
        ),
        "unanswered_request_items": _string_list(
            extracted.get("unanswered_request_items")
        ),
        "first_response_evidence": first_response_evidence,
        "attention_reason": str(
            extracted.get("attention_reason") or ""
        ).strip(),
        "model_version": LLMService.DEEPSEEK_MODEL,
        "analysis_version": ANALYSIS_VERSION,
    }
