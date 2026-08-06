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
