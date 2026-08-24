"""Detección determinista del código de propiedad en la plantilla inicial."""

import re
import unicodedata


PROPERTY_CODE_RE = re.compile(r"\bPROP\s*0*(\d{1,9})\b", re.IGNORECASE)
TITLE_RE = re.compile(
    r"m[aá]s\s+info(?:rmaci[oó]n)?\s+sobre\s+(?:el|la)\s+(.+?)\s*\(\s*PROP",
    re.IGNORECASE,
)
STOPWORDS = {
    "casa", "departamento", "depa", "terreno", "local", "comercial",
    "en", "de", "del", "la", "el", "urb", "urbanizacion", "proyecto",
}


def extract_property_identity(text):
    matches = PROPERTY_CODE_RE.findall(text or "")
    codes = sorted({f"PROP{int(value):06d}" for value in matches})
    title_match = TITLE_RE.search(text or "")
    return {"codes": codes, "title_hint": title_match.group(1).strip() if title_match else ""}


_CAPTACION_PATTERNS = (
    r"quiero\s+vender",
    r"vender\s+(?:mi|una\s+|un\s+|el\s+|la\s+)?(?:propiedad|casa|departamento|depa|terreno|local)",
    r"estoy\s+vendiendo",
    r"\bvendo\s+(?:mi\s+|una\s+|un\s+|el\s+|la\s+)?(?:propiedad|casa|departamento|depa|terreno|local)",
    r"poner\s+(?:mi\s+|en\s+venta)",
    r"tasaci[oó]n",
    r"cu[aá]nto\s+(?:vale|me\s+(?:dan|ofrecen|pagar[ií]an))\s+(?:mi\s+|mi\s+propiedad|por\s+mi\s+)?(?:casa|departamento|depa|terreno|local|propiedad)?",
)
_CAPTACION_RE = re.compile("|".join(_CAPTACION_PATTERNS), re.IGNORECASE)


def detect_captacion_intent(text):
    """True si el mensaje expresa intención de VENDER una propiedad (captación).

    Los mensajes de captación ("¡Hola! Quiero vender una propiedad.", "vendo
    mi terreno", "¿cuánto me dan por mi casa?") NO traen código PROP, por lo
    que hoy caen en NO_PROPERTY_CODE y no reciben respuesta.
    """
    return bool(text and _CAPTACION_RE.search(text))


def _tokens(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    words = re.findall(r"[a-z0-9]+", normalized.lower())
    return {word for word in words if len(word) > 1 and word not in STOPWORDS}


def title_is_consistent(title_hint, property_title):
    hint_tokens = _tokens(title_hint)
    if not hint_tokens:
        return True
    title_tokens = _tokens(property_title)
    return bool(title_tokens) and len(hint_tokens & title_tokens) / len(hint_tokens) >= 0.34
