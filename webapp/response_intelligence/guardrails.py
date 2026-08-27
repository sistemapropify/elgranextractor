"""Guardrails deterministas obligatorios del motor de respuestas IA.

Spec §7: se aplican SIEMPRE (sandbox, shadow y producción), independientemente
de la fase, y no confían solo en que el modelo obedezca el prompt: validan la
salida generada con regex y reglas simples de texto.

Chequeos:
1. Escalamiento: si el mensaje del cliente contiene palabras de riesgo legal o
   urgencia (abogado, denuncia, urgente, cancelar contrato...), el motor NUNCA
   genera con IA: se deja a una respuesta breve y empática de revisión, sin
   anunciar agentes ni repetir frases de derivación.
2. Alucinación determinista: si no se inyectaron datos de la propiedad
   (``property_data_used`` vacío) pero la respuesta menciona precio / m² /
   dirección, se marca ``hallucination`` y se bloquea el envío.
3. Negociación de precio: la regla "nunca negociar precio" se valida también con
   regex sobre montos / porcentajes de descuento, no solo en el prompt.

Todo es puro (sin BD) para poder testearlo sin tocar Azure.
"""

import re

# ------------------------------------------------------------------ #
# 1. Escalamiento
# ------------------------------------------------------------------ #
ESCALATION_KEYWORDS = (
    "abogado", "abogada", "denuncia", "urgente", "cancelar contrato",
    "cancelación", "cancelacion", "indecopi", "notaria", "notaría", "demanda",
    "juicio", "clausula", "cláusula", "estafa", "fraude", "policía", "police",
    "abuso", "discriminación", "discriminacion", "defensoría", "defensoria",
    "superintendencia", "arbitraje", "seguro legal", "inspectores",
)

_ESCALATION_RE = re.compile(
    r"\b(" + "|".join(ESCALATION_KEYWORDS) + r")\b", re.IGNORECASE
)


def is_escalation(text: str) -> bool:
    """True si el texto contiene palabras de escalamiento/riesgo legal."""
    return bool(_ESCALATION_RE.search(text or ""))


# ------------------------------------------------------------------ #
# 2. Mención de datos de la propiedad (precio / m² / dirección)
# ------------------------------------------------------------------ #
# Detecta montos (S/ US$ $ soles dólares), superficies (m²/m2/mts), y
# referencias de ubicación (avenida, calle, distrito...).
_MONEY_RE = re.compile(
    r"(S/|S\.|US\$|\$|USD|soles|dólares|dolares)?\s?"
    r"\d[\d.,]*\s?(soles|dólares|dolares|usd)?",
    re.IGNORECASE,
)
_AREA_RE = re.compile(
    r"\d[\d.,]*\s*(m²|m2|mts\s*2|metros\s+cuadrados|metros\s+2|m\.2)",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(
    r"\b(avenida|av\.?|calle|jr\.?|jirón|jiron|pasaje|urbanización|urbanizacion"
    r"|distrito|ubicación|ubicacion|dirección|direccion|referencia|cerca de)\b",
    re.IGNORECASE,
)
_PRECIO_WORD_RE = re.compile(r"\b(precio|costo|cuesta|valor|cuánto)\b", re.IGNORECASE)


def mentions_property_data(text: str) -> bool:
    """True si el texto menciona precio / superficie / ubicación concreta.

    Se usa contra la respuesta generada para detectar alucinaciones cuando no se
    inyectaron datos reales de la propiedad.
    """
    value = text or ""
    return bool(
        _MONEY_RE.search(value)
        or _AREA_RE.search(value)
        or _LOCATION_RE.search(value)
        or _PRECIO_WORD_RE.search(value)
    )


# ------------------------------------------------------------------ #
# 3. Negociación de precio (descuentos / rebajas / porcentajes)
# ------------------------------------------------------------------ #
_DISCOUNT_WORD_RE = re.compile(
    r"\b(descuento|rebaja|regatear|regateo|bajar|bajaría|bajaria|menor precio"
    r"|precio menor|negociar|oferta especial|precio especial)\b",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\d{1,3}\s*(%|por\s+ciento)", re.IGNORECASE)
# Monto precedido de "a", "en" o "por" tras verbo de rebaja, ej. "a S/ 90,000".
_DISCOUNT_AMOUNT_RE = re.compile(
    r"\b(a|en|por)\s+(S/|US\$|\$|USD|soles|dólares|dolares)?\s?\d[\d.,]*",
    re.IGNORECASE,
)


def mentions_discount(text: str) -> bool:
    """True si la respuesta intenta negociar precio (descuento/rebaja/%).

    Complementa la BusinessRule 'nunca negociar precio' con un check de
    post-procesamiento: no se confía solo en que el modelo obedezca el prompt.
    """
    value = text or ""
    return bool(
        _DISCOUNT_WORD_RE.search(value)
        or _PERCENT_RE.search(value)
        or _DISCOUNT_AMOUNT_RE.search(value)
    )


# ------------------------------------------------------------------ #
# Validación completa de una respuesta generada
# ------------------------------------------------------------------ #
def validate_generated_response(generated_response: str, property_data_used: list) -> dict:
    """Valida la respuesta generada y devuelve los flags de guardrail.

    Devuelve::

        {
          "hallucination": bool,   # menciona datos sin que se inyectaran
          "escalation": bool,      # la respuesta escala (no debería pasar)
          "discount": bool,        # intenta negociar precio
          "blocked": bool,         # True si no se debe enviar
          "reasons": [str, ...],   # motivos legibles para el dashboard
        }
    """
    response = generated_response or ""
    has_data = bool(property_data_used)
    hallucination = bool(response) and (not has_data) and mentions_property_data(response)
    escalation = is_escalation(response)
    discount = mentions_discount(response)

    reasons = []
    if hallucination:
        reasons.append(
            "Alucinación: menciona precio/m²/dirección sin datos de la propiedad"
        )
    if escalation:
        reasons.append("Contenido de escalamiento/riesgo legal")
    if discount:
        reasons.append("Negocia precio (prohibido por regla de negocio)")

    blocked = bool(reasons)
    return {
        "hallucination": hallucination,
        "escalation": escalation,
        "discount": discount,
        "blocked": blocked,
        "reasons": reasons,
    }


def block_summary(validation: dict) -> str:
    """Frase corta legible del motivo de bloqueo (para el dashboard)."""
    if not validation.get("blocked"):
        return ""
    return "; ".join(validation.get("reasons") or [])
