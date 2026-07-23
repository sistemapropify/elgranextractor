"""Aplicación segura en memoria de condiciones estructuradas."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from .contracts import AppliedFilter, FilterCondition, FilterOperator


def apply_conditions(
    items: Iterable[dict[str, Any]],
    conditions: list[FilterCondition],
) -> tuple[list[dict[str, Any]], list[AppliedFilter]]:
    current = list(items)
    evidence = []

    for condition in conditions:
        before = len(current)
        current = [
            item for item in current
            if _matches(_field_values(item).get(condition.field_name), condition)
        ]
        evidence.append(AppliedFilter(
            logical_name=condition.logical_name,
            field_name=condition.field_name,
            operator=condition.operator.value,
            requested_value=condition.value,
            matched_count_before=before,
            matched_count_after=len(current),
            execution_mode='python_safe',
        ))

    return current, evidence


def _field_values(item: dict[str, Any]) -> dict[str, Any]:
    values = item.get('field_values')
    return values if isinstance(values, dict) else item


def _matches(actual: Any, condition: FilterCondition) -> bool:
    if actual is None:
        return False

    if condition.value_type in {'decimal', 'integer'}:
        try:
            left = Decimal(str(actual))
            right = Decimal(str(condition.value))
        except (InvalidOperation, TypeError, ValueError):
            return False
    else:
        left = str(actual).strip().casefold()
        right = str(condition.value).strip().casefold()

    if condition.operator == FilterOperator.EQ:
        return left == right
    if condition.operator == FilterOperator.LTE:
        return left <= right
    if condition.operator == FilterOperator.GTE:
        return left >= right
    if condition.operator == FilterOperator.IN:
        return left in right
    if condition.operator == FilterOperator.ICONTAINS:
        return right in left
    return False
