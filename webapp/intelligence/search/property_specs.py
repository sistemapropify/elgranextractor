"""Enriquecimiento de resultados RAG con especificaciones relacionales."""

from __future__ import annotations

import logging
from typing import Any

from django.db import connections

logger = logging.getLogger(__name__)

SPEC_COLUMNS = (
    'bedrooms',
    'bathrooms',
    'half_bathrooms',
    'land_area',
    'built_area',
    'garage_spaces',
)


def enrich_property_results(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Añade `property_specs` sin modificar la base ni perder metadatos RAG."""
    ids = {
        property_id
        for item in items
        if (property_id := _property_id(item)) is not None
    }
    if not ids:
        return items

    specs_by_id: dict[int, dict[str, Any]] = {}
    try:
        ordered_ids = sorted(ids)
        placeholders = ', '.join(['%s'] * len(ordered_ids))
        with connections['propifai'].cursor() as cursor:
            cursor.execute(
                f"""
                SELECT property_id, {', '.join(SPEC_COLUMNS)}
                FROM property_specs
                WHERE property_id IN ({placeholders})
                """,
                ordered_ids,
            )
            for row in cursor.fetchall():
                specs_by_id[int(row[0])] = dict(zip(SPEC_COLUMNS, row[1:]))
    except Exception:
        logger.exception("No se pudieron enriquecer resultados con property_specs")
        return items

    for item in items:
        specs = specs_by_id.get(_property_id(item))
        if not specs:
            continue
        fields = dict(item.get('field_values') or {})
        fields.update({key: value for key, value in specs.items() if value is not None})
        item['field_values'] = fields
    return items


def _property_id(item: dict[str, Any]) -> int | None:
    fields = item.get('field_values') or {}
    raw_id = fields.get('id') or item.get('source_id')
    try:
        return int(raw_id)
    except (TypeError, ValueError):
        return None
