"""Motor determinista general para ejecutar restricciones semánticas validadas."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import unicodedata
from typing import Any, Iterable

from .contracts import (
    ConstraintOperator,
    OperandKind,
    SemanticConstraint,
    SemanticOperand,
    SemanticTaskState,
)


_FIELD_ALIASES = {
    "property_type": ("property_type", "property_type_name", "tipo_propiedad"),
    "district": ("district", "district_name", "distrito"),
    "operation": ("operation", "operation_type_name", "operacion"),
    "status": (
        "status",
        "property_status_name",
        "property_condition_name",
        "condicion",
        "estado",
    ),
    "currency": ("currency", "currency_name", "moneda"),
    "price": ("price", "precio", "sale_price", "precio_venta"),
    "bedrooms": ("bedrooms", "habitaciones", "dormitorios"),
    "bathrooms": ("bathrooms", "banos", "baños"),
    "half_bathrooms": ("half_bathrooms", "medios_banos"),
    "land_area": ("land_area", "area_terreno"),
    "built_area": ("built_area", "area_construida"),
    "garage_spaces": ("garage_spaces", "estacionamientos", "cocheras"),
    "antiquity_years": ("antiquity_years", "antiguedad"),
    "title": ("title", "titulo"),
    "description": ("description", "descripcion"),
}

_NUMERIC_FIELDS = {
    "price",
    "bedrooms",
    "bathrooms",
    "half_bathrooms",
    "land_area",
    "built_area",
    "garage_spaces",
    "antiquity_years",
}


@dataclass(frozen=True)
class ConstraintEvaluation:
    constraint_id: str
    matched: bool
    status: str
    left_value: Any = None
    right_value: Any = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "matched": self.matched,
            "status": self.status,
            "left_value": self.left_value,
            "right_value": self.right_value,
            "reason": self.reason,
        }


@dataclass
class EntityEvaluation:
    matched: bool
    checks: list[ConstraintEvaluation] = field(default_factory=list)

    @property
    def satisfied_count(self) -> int:
        return sum(1 for item in self.checks if item.matched)

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "satisfied_count": self.satisfied_count,
            "constraint_count": len(self.checks),
            "checks": [item.to_dict() for item in self.checks],
        }


class SemanticConstraintEngine:
    """Evalúa expresiones; no interpreta lenguaje natural ni toma decisiones LLM."""

    @classmethod
    def evaluate(
        cls,
        entity: dict[str, Any],
        task_or_constraints: SemanticTaskState | Iterable[SemanticConstraint],
    ) -> EntityEvaluation:
        entity = cls._canonical_entity(entity)
        constraints = (
            task_or_constraints.constraints
            if isinstance(task_or_constraints, SemanticTaskState)
            else list(task_or_constraints)
        )
        checks = [
            cls.evaluate_constraint(entity, constraint)
            for constraint in constraints
        ]
        matched = all(
            check.matched or not constraint.required
            for check, constraint in zip(checks, constraints)
        )
        return EntityEvaluation(matched=matched, checks=checks)

    @staticmethod
    def _canonical_entity(entity: dict[str, Any]) -> dict[str, Any]:
        """Aplana el sobre estándar de las skills sin perder metadatos raíz."""
        if not isinstance(entity, dict):
            return {}
        fields = entity.get("field_values")
        if not isinstance(fields, dict):
            return entity
        canonical = dict(entity)
        canonical.update(fields)
        return canonical

    @classmethod
    def filter(
        cls,
        entities: Iterable[dict[str, Any]],
        task_or_constraints: SemanticTaskState | Iterable[SemanticConstraint],
    ) -> tuple[list[dict[str, Any]], list[EntityEvaluation]]:
        matched_entities = []
        evaluations = []
        for entity in entities:
            evaluation = cls.evaluate(entity, task_or_constraints)
            evaluations.append(evaluation)
            if evaluation.matched:
                matched_entities.append(entity)
        return matched_entities, evaluations

    @classmethod
    def evaluate_constraint(
        cls,
        entity: dict[str, Any],
        constraint: SemanticConstraint,
    ) -> ConstraintEvaluation:
        left_found, left_value = cls._resolve_operand(entity, constraint.left)
        right_found, right_value = cls._resolve_operand(entity, constraint.right)
        if not left_found or not right_found:
            missing = []
            if not left_found:
                missing.append("left")
            if not right_found:
                missing.append("right")
            return ConstraintEvaluation(
                constraint_id=constraint.id,
                matched=False,
                status="missing_operand",
                left_value=left_value,
                right_value=right_value,
                reason=f"Operandos ausentes: {', '.join(missing)}",
            )

        try:
            matched = cls._compare(
                constraint.operator,
                left_value,
                right_value,
                left_field=(
                    str(constraint.left.value)
                    if constraint.left.kind == OperandKind.FIELD
                    else ""
                ),
                right_field=(
                    str(constraint.right.value)
                    if constraint.right.kind == OperandKind.FIELD
                    else ""
                ),
            )
        except (InvalidOperation, TypeError, ValueError) as exc:
            return ConstraintEvaluation(
                constraint_id=constraint.id,
                matched=False,
                status="invalid_value",
                left_value=left_value,
                right_value=right_value,
                reason=f"{type(exc).__name__}: {str(exc)[:120]}",
            )
        return ConstraintEvaluation(
            constraint_id=constraint.id,
            matched=bool(matched),
            status="matched" if matched else "not_matched",
            left_value=left_value,
            right_value=right_value,
        )

    @classmethod
    def _resolve_operand(
        cls,
        entity: dict[str, Any],
        operand: SemanticOperand,
    ) -> tuple[bool, Any]:
        if operand.kind in {OperandKind.LITERAL, OperandKind.SET}:
            return True, operand.value
        if operand.kind != OperandKind.FIELD:
            return False, None
        field_name = str(operand.value)
        for alias in _FIELD_ALIASES.get(field_name, (field_name,)):
            if alias in entity and entity[alias] not in (None, ""):
                return True, entity[alias]
        return False, None

    @classmethod
    def _compare(
        cls,
        operator: ConstraintOperator,
        left: Any,
        right: Any,
        *,
        left_field: str = "",
        right_field: str = "",
    ) -> bool:
        numeric = (
            left_field in _NUMERIC_FIELDS
            or right_field in _NUMERIC_FIELDS
            or operator in {
                ConstraintOperator.GT,
                ConstraintOperator.GTE,
                ConstraintOperator.LT,
                ConstraintOperator.LTE,
                ConstraintOperator.BETWEEN,
            }
        )
        if operator == ConstraintOperator.IN:
            return any(cls._equal(left, value, numeric=numeric) for value in right)
        if operator == ConstraintOperator.NOT_IN:
            return all(not cls._equal(left, value, numeric=numeric) for value in right)
        if operator == ConstraintOperator.BETWEEN:
            if not isinstance(right, (list, tuple)) or len(right) != 2:
                raise ValueError("BETWEEN requiere exactamente dos límites")
            left_n = cls._decimal(left)
            return cls._decimal(right[0]) <= left_n <= cls._decimal(right[1])
        if operator == ConstraintOperator.CONTAINS:
            return cls._text(right) in cls._text(left)
        if operator == ConstraintOperator.EQ:
            return cls._equal(left, right, numeric=numeric)
        if operator == ConstraintOperator.NEQ:
            return not cls._equal(left, right, numeric=numeric)

        left_n = cls._decimal(left)
        right_n = cls._decimal(right)
        if operator == ConstraintOperator.GT:
            return left_n > right_n
        if operator == ConstraintOperator.GTE:
            return left_n >= right_n
        if operator == ConstraintOperator.LT:
            return left_n < right_n
        if operator == ConstraintOperator.LTE:
            return left_n <= right_n
        raise ValueError(f"Operador no soportado: {operator}")

    @classmethod
    def _equal(cls, left: Any, right: Any, *, numeric: bool) -> bool:
        if numeric:
            return cls._decimal(left) == cls._decimal(right)
        return cls._text(left) == cls._text(right)

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        if isinstance(value, bool):
            raise InvalidOperation("boolean no es un número inmobiliario")
        normalized = str(value).strip().replace(",", "")
        return Decimal(normalized)

    @staticmethod
    def _text(value: Any) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        return "".join(
            char for char in normalized if not unicodedata.combining(char)
        ).casefold().strip()
