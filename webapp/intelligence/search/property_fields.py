"""Lectura canónica de campos inmobiliarios usados por todas las capas."""

from __future__ import annotations

from typing import Any, Mapping, Tuple


LAND_AREA_FIELDS = (
    "land_area",
    "area_terreno",
    "total_area",
    "area",
)
BUILT_AREA_FIELDS = (
    "built_area",
    "area_construida",
    "total_area",
    "area",
    "land_area",
    "area_terreno",
)


def property_type_value(fields: Mapping[str, Any]) -> str:
    return str(
        fields.get("property_type_name")
        or fields.get("tipo_propiedad")
        or fields.get("property_type")
        or ""
    ).strip()


def canonical_property_area(
    fields: Mapping[str, Any],
    property_type: Any = None,
) -> Tuple[Any, str | None]:
    """Devuelve el área comercial correcta y el campo que la respalda."""

    normalized_type = str(
        property_type if property_type not in (None, "")
        else property_type_value(fields)
    ).casefold()
    candidates = (
        LAND_AREA_FIELDS if "terreno" in normalized_type else BUILT_AREA_FIELDS
    )
    for field_name in candidates:
        value = fields.get(field_name)
        if value not in (None, ""):
            return value, field_name
    return None, None
