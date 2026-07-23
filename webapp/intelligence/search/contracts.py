"""Tipos canónicos que preservan la semántica de los filtros."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from decimal import Decimal
from typing import Any, Optional


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


class FilterOperator(str, Enum):
    EQ = 'eq'
    LTE = 'lte'
    GTE = 'gte'
    IN = 'in'
    ICONTAINS = 'icontains'


@dataclass(frozen=True)
class FilterCondition:
    logical_name: str
    field_name: str
    operator: FilterOperator
    value: Any
    value_type: str
    required: bool = True
    source: str = 'current_message'
    currency: Optional[str] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data['operator'] = self.operator.value
        data['value'] = _json_safe(data['value'])
        return data


@dataclass
class SearchPlan:
    query: str
    collections: list[str]
    conditions: list[FilterCondition] = field(default_factory=list)
    semantic_query: str = ''
    top_k: int = 9999
    schema_version: str = '1'

    def equality_filters(self) -> dict[str, Any]:
        """Adaptador temporal para el prefiltrado ORM no ambiguo."""
        return {
            condition.field_name: condition.value
            for condition in self.conditions
            if condition.operator == FilterOperator.EQ
        }

    def to_params(self) -> dict[str, Any]:
        """Reconstruye parámetros normalizados para skills legacy."""
        params = {
            condition.logical_name: _json_safe(condition.value)
            for condition in self.conditions
        }
        currency = next(
            (condition.currency for condition in self.conditions if condition.currency),
            None,
        )
        if currency:
            params['moneda'] = currency
        if self.semantic_query:
            params['semantic_query'] = self.semantic_query
        return params

    def fingerprint(self) -> str:
        payload = json.dumps(
            self.to_dict(),
            sort_keys=True,
            ensure_ascii=True,
            separators=(',', ':'),
        )
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]

    @classmethod
    def from_dict(cls, data: dict) -> 'SearchPlan':
        return cls(
            query=data.get('query', ''),
            collections=list(data.get('collections') or []),
            conditions=[
                FilterCondition(
                    logical_name=item['logical_name'],
                    field_name=item['field_name'],
                    operator=FilterOperator(item['operator']),
                    value=item.get('value'),
                    value_type=item.get('value_type', 'string'),
                    required=item.get('required', True),
                    source=item.get('source', 'current_message'),
                    currency=item.get('currency'),
                )
                for item in data.get('conditions', [])
            ],
            semantic_query=data.get('semantic_query', ''),
            top_k=int(data.get('top_k', 9999)),
            schema_version=str(data.get('schema_version', '1')),
        )

    def to_dict(self) -> dict:
        return {
            'query': self.query,
            'collections': self.collections,
            'conditions': [condition.to_dict() for condition in self.conditions],
            'semantic_query': self.semantic_query,
            'top_k': self.top_k,
            'schema_version': self.schema_version,
        }


@dataclass(frozen=True)
class AppliedFilter:
    logical_name: str
    field_name: str
    operator: str
    requested_value: Any
    matched_count_before: int
    matched_count_after: int
    execution_mode: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data['requested_value'] = _json_safe(data['requested_value'])
        return data
