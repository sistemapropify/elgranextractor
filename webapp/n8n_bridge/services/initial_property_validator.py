"""Guardrails deterministas antes de publicar la respuesta."""

from .initial_property_renderer import TEMPLATES


ALLOWED_FIELDS = {
    "casa": {"bedrooms", "built_area", "bathrooms"},
    "departamento": {"bedrooms", "built_area", "bathrooms"},
    "terreno": {"land_area"},
    "local_comercial": {"built_area", "bathrooms", "garage_spaces"},
}


def validate_property_payload(data):
    property_type = data.get("property_type")
    if property_type not in TEMPLATES:
        return False, "UNSUPPORTED_PROPERTY_TYPE"
    if not data.get("location") or not data.get("price"):
        return False, "MISSING_REQUIRED_DATA"
    features = data.get("features") or []
    if not features or len(features) > 2:
        return False, "MISSING_REQUIRED_DATA"
    if any(item.get("field") not in ALLOWED_FIELDS[property_type] for item in features):
        return False, "VALIDATION_FAILED"
    if property_type == "terreno" and features[0].get("field") != "land_area":
        return False, "VALIDATION_FAILED"
    if data["price"].get("currency") not in {"USD", "PEN"}:
        return False, "MISSING_REQUIRED_DATA"
    return True, "ANSWER_SENT"


def validate_rendered_response(text, data):
    return bool(
        text
        and text.count("¡Gracias por escribirnos!") == 1
        and data["location"] in text
        and "Apenas uno de nuestros asesores esté disponible" in text
    )
