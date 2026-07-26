"""Contratos deterministas para artefactos de propiedades del Chat Web."""

from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional
import urllib.parse
import uuid

from ..search.property_fields import canonical_property_area


MEDIA_BASE = "https://propifymedia01.blob.core.windows.net/media"


def _number(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> Optional[int]:
    number = _number(value)
    return int(number) if number is not None else None


def _currency(value: Any) -> Optional[str]:
    normalized = str(value or "").strip().upper()
    if normalized in {"USD", "DOLAR", "DOLARES", "DÓLAR", "DÓLARES", "$"}:
        return "USD"
    if normalized in {"PEN", "SOL", "SOLES", "S/"}:
        return "PEN"
    return normalized or None


def _first(fields: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = fields.get(key)
        if value not in (None, ""):
            return value
    return None


def _image_from_code(code: Any) -> List[Dict[str, Any]]:
    if not code:
        return []
    code = str(code).strip()
    suffixes = (".jpg", ".jpeg", ".png", ".webp")
    filename = code if code.lower().endswith(suffixes) else f"{code}.jpg"
    return [{
        "url": f"{MEDIA_BASE}/{filename}",
        "alt": f"Propiedad {code}",
        "is_primary": True,
    }]


def _media_url(path: Any) -> Optional[str]:
    if not path:
        return None
    path = str(path).strip()
    if path.startswith(("https://", "http://")):
        return path
    encoded = "/".join(
        urllib.parse.quote(part) for part in path.lstrip("/").split("/")
    )
    return f"{MEDIA_BASE}/{encoded}"


def _hydrate_real_gallery(items: List[Dict[str, Any]]) -> None:
    """Carga solo la portada; la galería completa se obtiene en el detalle."""
    numeric_ids = []
    for item in items:
        try:
            numeric_ids.append(int(item["id"]))
        except (KeyError, TypeError, ValueError):
            continue
    if not numeric_ids:
        return

    try:
        from propifai.models import PropertyImage
        rows = PropertyImage.objects.using("propifai").filter(
            property_id__in=numeric_ids
        ).order_by("property_id", "id")
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            url = _media_url(row.image)
            if not url:
                continue
            property_id = str(row.property_id)
            gallery = grouped.setdefault(property_id, [])
            if gallery:
                continue
            gallery.append({
                "url": url,
                "alt": f"Fotografía de propiedad {property_id}",
                "is_primary": len(gallery) == 0,
            })
        for item in items:
            real_gallery = grouped.get(item["id"])
            if real_gallery:
                item["images"] = real_gallery
    except Exception:
        # La búsqueda sigue siendo utilizable si la BD externa no está disponible.
        return


def normalize_property_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fields = item.get("field_values")
    if not isinstance(fields, dict):
        fields = item

    source_id = _first(
        item,
        "source_id",
    )
    if source_id in (None, ""):
        source_id = _first(fields, "_source_id", "id", "property_id")
    if source_id in (None, ""):
        return None

    code = _first(fields, "code", "codigo")
    price = _number(_first(fields, "price", "precio", "precio_usd"))
    property_type = _first(fields, "property_type_name", "tipo_propiedad")
    canonical_area, _ = canonical_property_area(fields, property_type)
    area = _number(canonical_area)
    latitude = _number(_first(fields, "latitude", "lat"))
    longitude = _number(_first(fields, "longitude", "lng", "lon"))
    currency = _currency(_first(fields, "currency_name", "currency", "moneda"))

    return {
        "id": str(source_id),
        "code": str(code) if code not in (None, "") else None,
        "title": str(_first(fields, "title", "titulo") or f"Propiedad {source_id}"),
        "property_type": property_type,
        "operation_type": _first(fields, "operation_type_name", "tipo_operacion"),
        "status": _first(fields, "property_status_name", "estado"),
        "district": _first(fields, "district_name", "distrito"),
        "address": _first(fields, "display_address", "map_address", "direccion"),
        "price": price,
        "currency": currency,
        "area_m2": area,
        "bedrooms": _integer(_first(fields, "bedrooms", "numero_habitaciones")),
        "bathrooms": _number(_first(fields, "bathrooms", "numero_banos")),
        "parking_spaces": _integer(_first(fields, "garage_spaces", "numero_cocheras")),
        "description": str(fields.get("description") or fields.get("descripcion") or ""),
        "images": _image_from_code(code),
        "location": {"latitude": latitude, "longitude": longitude},
        "source": {
            "collection": item.get("collection_name"),
            "source_id": str(source_id),
            "updated_at": item.get("created_at"),
        },
    }


def build_property_collection_artifact(
    items: Iterable[Dict[str, Any]],
    *,
    message_id: str,
    trace_id: str = "",
    title: str = "Propiedades encontradas",
    hydrate_media: bool = True,
) -> Optional[Dict[str, Any]]:
    normalized = [
        result for result in (normalize_property_item(item) for item in items)
        if result is not None
    ]
    if not normalized:
        return None
    if hydrate_media:
        _hydrate_real_gallery(normalized)

    has_coordinates = any(
        item["location"]["latitude"] is not None
        and item["location"]["longitude"] is not None
        for item in normalized
    )
    views = ["cards", "table"]
    if has_coordinates:
        views.append("map")
    if len(normalized) >= 2:
        views.append("compare")

    def group_counts(field: str) -> List[Dict[str, Any]]:
        grouped: Dict[str, Dict[str, Any]] = {}
        for item in normalized:
            label = str(item.get(field) or "Sin especificar").strip()
            key = label.casefold()
            group = grouped.setdefault(key, {
                "key": key,
                "label": label,
                "count": 0,
                "types": {},
            })
            group["count"] += 1
            if field == "district":
                property_type = str(
                    item.get("property_type") or "Sin especificar"
                ).strip()
                type_key = property_type.casefold()
                previous = group["types"].get(type_key, {}).get("count", 0)
                group["types"][type_key] = {
                    "label": property_type,
                    "count": previous + 1,
                }
        result = []
        for group in grouped.values():
            group["types"] = sorted(
                group["types"].values(),
                key=lambda entry: (-entry["count"], entry["label"]),
            )
            result.append(group)
        return sorted(
            result,
            key=lambda entry: (-entry["count"], entry["label"]),
        )

    page_size = 12
    if len(normalized) > page_size:
        display_mode = "grouped"
    else:
        display_mode = "cards"

    return {
        "schema_version": "1.0",
        "type": "property_collection",
        "id": f"properties-{uuid.uuid4()}",
        "message_id": str(message_id),
        "title": title,
        "summary": f"{len(normalized)} resultados verificados",
        "default_view": "cards",
        "available_views": views,
        "result_count": len(normalized),
        "display_mode": display_mode,
        "page_size": page_size,
        "groups": {
            "districts": group_counts("district"),
            "property_types": group_counts("property_type"),
        },
        "filters": [],
        "items": normalized,
        "provenance": {
            "skill": "busqueda_propiedades",
            "collection": normalized[0]["source"].get("collection"),
            "trace_id": trace_id,
            "grounded": True,
        },
    }
