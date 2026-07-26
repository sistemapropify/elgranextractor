"""Normaliza parámetros legacy a un plan de búsqueda sin perder operadores."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

from ..language.es_pe_real_estate import (
    DISTRICT_ALIASES,
    PROPERTY_TYPE_ALIASES,
    SPANISH_SMALL_NUMBERS,
)
from .contracts import FilterCondition, FilterOperator, SearchPlan


class InvalidFilterParameter(ValueError):
    """El filtro es conocido, pero su valor no puede normalizarse."""


class SearchPlanNormalizer:
    _SCHEMA = {
        'distrito': ('district_name', FilterOperator.EQ, 'string'),
        'tipo_propiedad': ('property_type_name', FilterOperator.EQ, 'string'),
        'operacion': ('operation_type_name', FilterOperator.EQ, 'string'),
        'condicion': ('property_status_name', FilterOperator.EQ, 'string'),
        'moneda': ('currency_name', FilterOperator.EQ, 'string'),
        'precio': ('price', FilterOperator.EQ, 'decimal'),
        'precio_min': ('price', FilterOperator.GTE, 'decimal'),
        'precio_max': ('price', FilterOperator.LTE, 'decimal'),
        'habitaciones': ('bedrooms', FilterOperator.EQ, 'integer'),
        'habitaciones_min': ('bedrooms', FilterOperator.GTE, 'integer'),
        'banos': ('bathrooms', FilterOperator.EQ, 'integer'),
        'banos_min': ('bathrooms', FilterOperator.GTE, 'integer'),
        'area_min': ('built_area', FilterOperator.GTE, 'decimal'),
        'area_max': ('built_area', FilterOperator.LTE, 'decimal'),
    }
    _DISTRICTS = (
        'Cerro Colorado', 'Jose Luis Bustamante', 'Mariano Melgar',
        'Yanahuara', 'Miraflores', 'Paucarpata', 'Sachaca', 'Cayma',
        'Cercado', 'Arequipa',
    )
    _PROPERTY_TYPES = {
        'construir un colegio': 'Terreno',
        'construir colegio': 'Terreno',
        'construir una escuela': 'Terreno',
        'construir escuela': 'Terreno',
        'tienda de abarrotes': 'Local',
        'tienda comercial': 'Local',
        'local para tienda': 'Local',
        'tienda': 'Local',
        'negocio': 'Local',
        'terreno': 'Terreno',
        'terrenos': 'Terreno',
        # Errores tipográficos frecuentes en consultas escritas rápidamente.
        'terreo': 'Terreno',
        'terreos': 'Terreno',
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
        **PROPERTY_TYPE_ALIASES,
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
            if logical_name == 'moneda':
                value = {
                    'USD': 'Dolares',
                    'PEN': 'Soles',
                }.get(str(value).strip().upper(), value)
            conditions.append(FilterCondition(
                logical_name=logical_name,
                field_name=field_name,
                operator=operator,
                value=cls._coerce(value, value_type, logical_name),
                value_type=value_type,
                source=source,
                currency=(
                    str(currency).upper()
                    if currency and field_name in {'price', 'currency_name'}
                    else None
                ),
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
        lowered = cls._normalize_money_expressions(lowered)
        params: dict[str, Any] = {}

        for alias, district in sorted(
            DISTRICT_ALIASES.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if re.search(rf'\b{re.escape(alias)}\b', lowered):
                params['distrito'] = district
                break

        for district in cls._DISTRICTS:
            if 'distrito' not in params and district.casefold() in lowered:
                params['distrito'] = district
                break

        # Las frases más específicas se evalúan primero.
        for variant, normalized in sorted(
            cls._PROPERTY_TYPES.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if re.search(rf'\b{re.escape(variant)}\b', lowered):
                params['tipo_propiedad'] = normalized
                break

        if (
            any(term in lowered for term in ('colegio', 'escuela'))
            and any(term in lowered for term in ('construir', 'instalar', 'implementar'))
        ):
            params.setdefault('tipo_propiedad', 'Terreno')
            params.setdefault('condicion', 'Disponible')

        if re.search(r'\bdisponibles?\b', lowered):
            params['condicion'] = 'Disponible'

        if re.search(r'\b(?:en\s+)?venta\b|\bcomprar\b|\bcompra\b', lowered):
            params['operacion'] = 'Venta'
        elif re.search(
            r'\b(?:en\s+)?alquiler\b|\balquilar\b|\brenta\b',
            lowered,
        ):
            params['operacion'] = 'Alquiler'

        number = r'(\d[\d.,]*)'
        money_unit = r'(?:usd|d[oó]lares?|pen|soles?|s\/|\$)'
        max_patterns = (
            rf'(?:precio|presupuesto)(?:\s+m[aá]ximo)?\s+(?:de\s+)?(?:{money_unit}\s*)?{number}',
            rf'(?:menos\s+de|menor(?:es)?\s+(?:a|de)|hasta|m[aá]ximo|no\s+m[aá]s\s+de)\s*(?:{money_unit}\s*)?{number}\s*{money_unit}',
            rf'{money_unit}\s*{number}\s*(?:o\s+menos|como\s+m[aá]ximo)',
        )
        min_patterns = (
            rf'(?:precio|presupuesto)(?:\s+m[ií]nimo)\s+(?:de\s+)?(?:{money_unit}\s*)?{number}',
            rf'(?:m[aá]s\s+de|mayor(?:es)?\s+(?:a|de)|desde|m[ií]nimo)\s*(?:{money_unit}\s*)?{number}\s*{money_unit}',
            rf'{money_unit}\s*{number}\s*(?:o\s+m[aá]s|como\s+m[ií]nimo)',
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

        rooms_minimum = re.search(
            rf'(?:m[ií]nimo(?:\s+de)?|al\s+menos|desde)\s+'
            rf'{number}\s*(?:dormitorios?|habitaciones?|cuartos?)',
            lowered,
        )
        rooms_greater = re.search(
            rf'(?:m[aá]s\s+de|mayor(?:es)?\s+(?:a|de))\s+'
            rf'{number}\s*(?:dormitorios?|habitaciones?|cuartos?)',
            lowered,
        )
        rooms = re.search(
            rf'{number}\s*(?:dormitorios?|habitaciones?|cuartos?)',
            lowered,
        )
        if rooms_greater:
            params['habitaciones_min'] = int(
                cls._parse_number(rooms_greater.group(1))
            ) + 1
        elif rooms_minimum:
            params['habitaciones_min'] = int(
                cls._parse_number(rooms_minimum.group(1))
            )
        elif rooms:
            params['habitaciones'] = int(cls._parse_number(rooms.group(1)))

        bathrooms = re.search(
            rf'{number}\s*(?:baños?|banos?|servicios?\s+higienicos?)',
            lowered,
        )
        if bathrooms:
            params['banos'] = int(cls._parse_number(bathrooms.group(1)))

        bathrooms_word = re.search(
            r'\b(' + '|'.join(SPANISH_SMALL_NUMBERS) + r')\s+'
            r'(?:baños?|banos?|servicios?\s+higienicos?)',
            lowered,
        )
        if bathrooms_word and 'banos' not in params:
            params['banos'] = SPANISH_SMALL_NUMBERS[bathrooms_word.group(1)]

        area_max_patterns = (
            rf'(?:menos\s+de|menor(?:es)?\s+(?:a|de)|hasta|m[aá]ximo|no\s+m[aá]s\s+de)\s+{number}\s*(?:m2|m²|metros?(?:\s+cuadrados?)?)',
            rf'(?:[aá]rea|superficie)\s+m[aá]xima\s+(?:de\s+)?{number}\s*(?:m2|m²|metros?(?:\s+cuadrados?)?)',
        )
        for pattern in area_max_patterns:
            match = re.search(pattern, lowered)
            if match:
                params['area_max'] = cls._parse_number(match.group(1))
                break

        area_min_patterns = (
            rf'(?:área|area)(?:\s+mínima|\s+minima)?\s+(?:de\s+)?{number}\s*(?:m2|m²|metros?(?:\s+cuadrados?)?)',
            rf'(?:mínimo|minimo|desde|más\s+de|mas\s+de)\s+{number}\s*(?:m2|m²|metros?(?:\s+cuadrados?)?)',
        )
        for pattern in area_min_patterns:
            match = re.search(pattern, lowered)
            if match:
                params['area_min'] = cls._parse_number(match.group(1))
                break

        if 'dólar' in lowered or 'dolar' in lowered or 'usd' in lowered or '$' in text:
            params['moneda'] = 'USD'
        elif 'soles' in lowered or 'pen' in lowered or 's/' in lowered:
            params['moneda'] = 'PEN'

        return params

    @staticmethod
    def _normalize_money_expressions(text: str) -> str:
        """Convierte variantes monetarias peruanas a ``<monto> dolares|soles``."""
        currency_patterns = (
            (r'(?:us\$|usd|\$)\s*(\d[\d.,]*)', 'dolares'),
            (r'(?:s\/\.?|pen)\s*(\d[\d.,]*)', 'soles'),
        )
        normalized = text
        for pattern, currency in currency_patterns:
            normalized = re.sub(
                pattern,
                lambda match: f"{match.group(1)} {currency}",
                normalized,
            )

        number_words = '|'.join(SPANISH_SMALL_NUMBERS)
        normalized = re.sub(
            rf'\b({number_words})\s+mil\b',
            lambda match: str(SPANISH_SMALL_NUMBERS[match.group(1)] * 1000),
            normalized,
        )
        normalized = re.sub(
            r'\b(\d[\d.,]*)\s*(?:mil|k)\b',
            lambda match: str(
                SearchPlanNormalizer._parse_number(match.group(1)) * 1000
            ),
            normalized,
        )
        return normalized

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
