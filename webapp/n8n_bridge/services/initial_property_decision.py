"""Decisión determinista compartida para el primer mensaje de una propiedad.

No persiste ni envía mensajes. El endpoint real y shadow_live consumen el mismo
resultado para impedir divergencias entre lo respondido y lo evaluado.
"""

from intelligence.agents.respuesta_inicial_whatsapp_agent import AgenteRespuestaInicialWhatsApp

from .initial_property_detector import extract_property_identity, title_is_consistent
from .initial_property_renderer import render_initial_response
from .initial_property_validator import validate_property_payload, validate_rendered_response

BLOCKED_STATUSES = {"vendida", "vendido", "pausada", "pausado", "no disponible"}


def _failure(reason_code, *, property_code="", evidence=None):
    return {
        "success": False,
        "reason_code": reason_code,
        "property_code": property_code,
        "data": {},
        "reply_text": "",
        "evidence": evidence or {},
    }


def decide_initial_property_response(text, config, context=None):
    """Resuelve por código exacto y produce una respuesta verificada."""
    identity = extract_property_identity(text)
    if not identity["codes"]:
        return _failure("NO_PROPERTY_CODE")
    if len(identity["codes"]) != 1:
        return _failure(
            "MULTIPLE_PROPERTY_CODES", evidence={"codes": identity["codes"]}
        )

    code = identity["codes"][0]
    skill_result = AgenteRespuestaInicialWhatsApp().resolve(
        code, {"channel": "whatsapp", **(context or {})}
    )
    if not skill_result.success:
        reason = (skill_result.metadata or {}).get("reason_code", "INTERNAL_ERROR")
        return _failure(
            reason, property_code=code, evidence=skill_result.metadata or {}
        )

    data = skill_result.data
    evidence = {"resolution": "exact_code"}
    if identity["title_hint"] and not title_is_consistent(
        identity["title_hint"], data["title"]
    ):
        evidence["warning"] = {
            "code": "TITLE_CODE_MISMATCH",
            "title_hint": identity["title_hint"],
            "property_title": data["title"],
        }

    enabled_types = set(getattr(config, "enabled_property_types", None) or [])
    if data["property_type"] != "propiedad" and data["property_type"] not in enabled_types:
        return _failure(
            "PROPERTY_TYPE_DISABLED",
            property_code=code,
            evidence={**evidence, "property_type": data["property_type"]},
        )

    status = str(data.get("property_status") or "").lower().strip()
    if data.get("is_visible") is False or status in BLOCKED_STATUSES:
        return _failure(
            "PROPERTY_NOT_PUBLISHABLE",
            property_code=code,
            evidence={**evidence, "property_status": status},
        )

    valid, reason = validate_property_payload(data)
    if not valid:
        return _failure(
            reason, property_code=code, evidence={**evidence, "data": data}
        )

    reply = render_initial_response(data, config)
    if not validate_rendered_response(reply, data):
        return _failure("VALIDATION_FAILED", property_code=code, evidence=evidence)

    return {
        "success": True,
        "reason_code": "ANSWER_READY",
        "property_code": code,
        "data": data,
        "reply_text": reply,
        "evidence": evidence,
    }
