"""Contratos compartidos para búsquedas estructuradas."""

from .contracts import AppliedFilter, FilterCondition, FilterOperator, SearchPlan
from .normalizer import SearchPlanNormalizer

__all__ = [
    'AppliedFilter',
    'FilterCondition',
    'FilterOperator',
    'SearchPlan',
    'SearchPlanNormalizer',
]
