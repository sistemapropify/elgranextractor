"""Normaliza parámetros legacy a un plan de búsqueda sin perder operadores."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

from .contracts import FilterCondition, FilterOperator, SearchPlan


class InvalidFilterParameter(ValueError):
    """El filtro es conocido, pero su valor no puede normalizarse."""


class SearchPlanNormalizer:
    _SCHEMA = {
        'distrito': ('district_name', FilterOperator.EQ, 'string'),
        'tipo_propiedad': ('property_type_name', FilterOperator.EQ, 'string'),
        'operacion': ('operation_type_name', FilterOperator.EQ, 'string'),
        'condicion': ('property_status_name', FilterOperator.EQ, 'string'),
        'precio': ('price', FilterOperator.EQ, 'decimal'),
        'precio_min': ('price', FilterOperator.GTE, 'decimal'),
        'precio_max': ('price', FilterOperator.LTE, 'decimal'),
        'habitaciones': ('bedrooms', FilterOperator.EQ, 'integer'),
        'habitaciones_min': ('bedrooms', FilterOperator.GTE, 'integer'),
        'area_min': ('built_area', FilterOperator.GTE, 'decimal'),
        'area_max': ('built_area', FilterOperator.LTE, 'decimal'),
    }
    _DISTRICTS = (
        'Cerro Colorado', 'Jose Luis Bustamante', 'Mariano Melgar',
        'Yanahuara', 'Miraflores', 'Paucarpata', 'Sachaca', 'Cayma',
        'Cercado', 'Arequipa',
    )
    _PROPERTY_TYPES = {
        'tienda de abarrotes': 'Local',
        'tienda comercial': 'Local',
        'local para tienda': 'Local',
        'tienda': 'Local',
        'negocio': 'Local',
        'terreno': 'Terreno',
        'terrenos': 'Terreno',
        'lote': 'Terreno',
        'lotes': 'Terreno',
        'departamento': 'Departamento',
        'departamentos': 'Departamento',
        'depa': 'Departamento',
        'casa': 'Casa',
        'casas': 'Casa',
        'oficina': 'Oficina',
        'oficinas': 'Oficina',
        'local comercial': 'Local',
        'locales': 'Local',
    }

    @classmethod
    def from_params(
        cls,
        query: str,
        params: dict[str, Any] | None,
        collections: list[str],
        *,
        source: str = 'current_message',
        top_k: int = 9999,
    ) -> SearchPlan:
        params = params or {}
        conditions = []
        currency = params.get('moneda') or params.get('currency')

        for logical_name, (field_name, operator, value_type) in cls._SCHEMA.items():
            value = params.get(logical_name)
            if value is None or value == '':
                continue
            conditions.append(FilterCondition(
                logical_name=logical_name,
                field_name=field_name,
                operator=operator,
                value=cls._coerce(value, value_type, logical_name),
                value_type=value_type,
                source=source,
                currency=str(currency).upper() if currency and field_name == 'price' else None,
            ))

        return SearchPlan(
            query=query,
            collections=collections,
            conditions=conditions,
            semantic_query=str(params.get('semantic_query') or query),
            top_k=top_k,
        )

    @classmethod
    def params_from_message(cls, message: str) -> dict[str, Any]:
        """Extracción determinista mínima para crear el plan antes del routing."""
        text = (message or '').strip()
        lowered = text.casefold()
        params: dict[str, Any] = {}

        for district in cls._DISTRICTS:
            if district.casefold() in lowered:
                params['distrito'] = district
                break

        # Las frases más específicas se evalúan primero.
        for variant, normalized in sorted(
            cls._PROPERTY_TYPES.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if re.search(rf'\b{re.escape(variant)}\b', lowered):
                params['tipo_propiedad'] = normalized
                break

        number = r'(\d[\d.,]*)'
        max_patterns = (
            rf'(?:menos\s+de|menor(?:es)?\s+(?:a|de)|hasta|máximo|maximo|no\s+más\s+de|no\s+mas\s+de)\s*(?:usd|\$|s\/)?\s*{number}',
            rf'(?:usd|\$|s\/)?\s*{number}\s*(?:o\s+menos|como\s+máximo|como\s+maximo)',
        )
        min_patterns = (
            rf'(?:más\s+de|mas\s+de|mayor(?:es)?\s+(?:a|de)|desde|mínimo|minimo)\s*(?:usd|\$|s\/)?\s*{number}',
        )
        for pattern in max_patterns:
            match = re.search(pattern, lowered)
            if match:
                params['precio_max'] = cls._parse_number(match.group(1))
                break
        for pattern in min_patterns:
            match = re.search(pattern, lowered)
            if match:
                params['precio_min'] = cls._parse_number(match.group(1))
                break

        rooms = re.search(
            rf'{number}\s*(?:dormitorios?|habitaciones?|cuartos?)',
            lowered,
        )
        if rooms:
            params['habitaciones'] = int(cls._parse_number(rooms.group(1)))

        if 'dólar' in lowered or 'dolar' in lowered or 'usd' in lowered or '$' in text:
            params['moneda'] = 'USD'
        elif 'soles' in lowered or 'pen' in lowered or 's/' in lowered:
            params['moneda'] = 'PEN'

        return params

    @staticmethod
    def _parse_number(raw: str) -> Decimal:
        value = raw.strip()
        if ',' in value and '.' in value:
            value = value.replace(',', '')
        elif value.count('.') > 1:
            value = value.replace('.', '')
        elif '.' in value:
            tail = value.rsplit('.', 1)[-1]
            if len(tail) == 3:
                value = value.replace('.', '')
        elif ',' in value:
            tail = value.rsplit(',', 1)[-1]
            value = value.replace(',', '' if len(tail) == 3 else '.')
        return Decimal(value)

    @staticmethod
    def _coerce(value: Any, value_type: str, logical_name: str) -> Any:
        try:
            if value_type == 'decimal':
                return Decimal(str(value))
            if value_type == 'integer':
                return int(value)
            return str(value).strip()
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise InvalidFilterParameter(
                f"INVALID_FILTER_PARAMETER: {logical_name}={value!r}"
            ) from exc
