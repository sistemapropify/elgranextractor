"""Validación estructural y semántica del contrato agentic v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import (
    ConstraintOperator,
    OperandKind,
    SemanticConstraint,
    SemanticTaskState,
)


PROPERTY_FIELDS: dict[str, str] = {
    "property_type": "string",
    "district": "string",
    "operation": "string",
    "status": "string",
    "currency": "string",
    "price": "decimal",
    "bedrooms": "integer",
    "bathrooms": "integer",
    "half_bathrooms": "integer",
    "land_area": "decimal",
    "built_area": "decimal",
    "garage_spaces": "integer",
    "antiquity_years": "integer",
    "title": "string",
    "description": "string",
}

NUMERIC_TYPES = {"integer", "decimal"}
ORDER_OPERATORS = {
    ConstraintOperator.GT,
    ConstraintOperator.GTE,
    ConstraintOperator.LT,
    ConstraintOperator.LTE,
    ConstraintOperator.BETWEEN,
}
SET_OPERATORS = {ConstraintOperator.IN, ConstraintOperator.NOT_IN}
VAGUE_LITERALS = {
    "poco", "pocos", "poca", "pocas", "barato", "barata", "baratos",
    "grande", "grandes", "pequeño", "pequeña", "cerca", "lejos",
    "económico", "economico", "amplio", "amplia",
}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: str
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "severity": self.severity,
        }


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(item.severity == "error" for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "issues": [item.to_dict() for item in self.issues],
        }


class SemanticTaskValidator:
    """Impide que un modelo invente campos, operadores o umbrales vagos."""

    @classmethod
    def validate(cls, task: SemanticTaskState) -> ValidationResult:
        result = ValidationResult()
        if not task.original_query.strip():
            result.issues.append(ValidationIssue(
                "EMPTY_QUERY", "La consulta original está vacía.", "original_query"
            ))
        if not task.entity.strip():
            result.issues.append(ValidationIssue(
                "EMPTY_ENTITY", "La entidad de la tarea está vacía.", "entity"
            ))

        seen_ids: set[str] = set()
        for index, constraint in enumerate(task.constraints):
            path = f"constraints[{index}]"
            if not constraint.id:
                result.issues.append(ValidationIssue(
                    "EMPTY_CONSTRAINT_ID", "La restricción no tiene ID.", f"{path}.id"
                ))
            elif constraint.id in seen_ids:
                result.issues.append(ValidationIssue(
                    "DUPLICATE_CONSTRAINT_ID",
                    f"El ID {constraint.id!r} está duplicado.",
                    f"{path}.id",
                ))
            seen_ids.add(constraint.id)
            cls._validate_constraint(constraint, path, result)

        ambiguity_ids: set[str] = set()
        for index, ambiguity in enumerate(task.ambiguities):
            path = f"ambiguities[{index}]"
            if not ambiguity.id or ambiguity.id in ambiguity_ids:
                result.issues.append(ValidationIssue(
                    "INVALID_AMBIGUITY_ID",
                    "La ambigüedad requiere un ID único.",
                    f"{path}.id",
                ))
            ambiguity_ids.add(ambiguity.id)
            if ambiguity.required and not ambiguity.clarification.strip():
                result.issues.append(ValidationIssue(
                    "MISSING_CLARIFICATION",
                    "Una ambigüedad obligatoria requiere una pregunta.",
                    f"{path}.clarification",
                ))
        transition = task.transition
        current_ids = {item.id for item in task.constraints if item.id}
        carried = set(transition.carried_constraint_ids)
        added = set(transition.added_constraint_ids)
        removed = set(transition.removed_constraint_ids)
        for label, values in (
            ("carried_constraint_ids", carried),
            ("added_constraint_ids", added),
        ):
            unknown = values - current_ids
            if unknown:
                result.issues.append(ValidationIssue(
                    "TRANSITION_REFERENCES_MISSING_CONSTRAINT",
                    f"{label} contiene IDs que no existen en el estado resultante.",
                    f"transition.{label}",
                ))
        overlap = (carried & added) | (carried & removed) | (added & removed)
        if overlap:
            result.issues.append(ValidationIssue(
                "OVERLAPPING_TRANSITION_IDS",
                "Una restricción no puede conservarse, agregarse y eliminarse a la vez.",
                "transition",
            ))
        if removed & current_ids:
            result.issues.append(ValidationIssue(
                "REMOVED_CONSTRAINT_STILL_PRESENT",
                "Una restricción declarada como eliminada sigue en el estado.",
                "transition.removed_constraint_ids",
            ))
        if (
            transition.relationship.value == "new_task"
            and (carried or removed)
        ):
            result.issues.append(ValidationIssue(
                "NEW_TASK_CANNOT_CARRY_PREVIOUS_CONSTRAINTS",
                "Una tarea nueva no debe conservar ni eliminar IDs anteriores.",
                "transition",
            ))

        return result

    @classmethod
    def _validate_constraint(
        cls,
        constraint: SemanticConstraint,
        path: str,
        result: ValidationResult,
    ) -> None:
        if constraint.left.kind != OperandKind.FIELD:
            result.issues.append(ValidationIssue(
                "LEFT_OPERAND_MUST_BE_FIELD",
                "El operando izquierdo debe ser un campo.",
                f"{path}.left",
            ))
            return

        left_name = str(constraint.left.value or "")
        left_type = PROPERTY_FIELDS.get(left_name)
        if not left_type:
            result.issues.append(ValidationIssue(
                "UNKNOWN_FIELD",
                f"El campo {left_name!r} no pertenece al esquema autorizado.",
                f"{path}.left.value",
            ))
            return

        if constraint.right.kind == OperandKind.FIELD:
            right_name = str(constraint.right.value or "")
            right_type = PROPERTY_FIELDS.get(right_name)
            if not right_type:
                result.issues.append(ValidationIssue(
                    "UNKNOWN_FIELD",
                    f"El campo {right_name!r} no pertenece al esquema autorizado.",
                    f"{path}.right.value",
                ))
            elif constraint.operator in ORDER_OPERATORS and (
                left_type not in NUMERIC_TYPES or right_type not in NUMERIC_TYPES
            ):
                result.issues.append(ValidationIssue(
                    "INCOMPARABLE_FIELDS",
                    "Las comparaciones de orden entre campos requieren valores numéricos.",
                    path,
                ))

        if constraint.operator in SET_OPERATORS:
            values = constraint.right.value
            if constraint.right.kind != OperandKind.SET or not isinstance(values, list):
                result.issues.append(ValidationIssue(
                    "SET_OPERAND_REQUIRED",
                    "Los operadores IN/NOT_IN requieren un conjunto.",
                    f"{path}.right",
                ))
            elif not values:
                result.issues.append(ValidationIssue(
                    "EMPTY_SET", "El conjunto no puede estar vacío.", f"{path}.right"
                ))

        if constraint.operator == ConstraintOperator.BETWEEN:
            values = constraint.right.value
            if (
                constraint.right.kind != OperandKind.SET
                or not isinstance(values, list)
                or len(values) != 2
            ):
                result.issues.append(ValidationIssue(
                    "BETWEEN_REQUIRES_TWO_VALUES",
                    "BETWEEN requiere exactamente dos límites.",
                    f"{path}.right",
                ))

        if (
            constraint.operator in ORDER_OPERATORS
            and constraint.right.kind == OperandKind.LITERAL
            and left_type not in NUMERIC_TYPES
        ):
            result.issues.append(ValidationIssue(
                "ORDER_ON_NON_NUMERIC_FIELD",
                f"El campo {left_name!r} no admite comparación numérica.",
                path,
            ))

        if constraint.right.kind == OperandKind.LITERAL:
            normalized = str(constraint.right.value or "").casefold().strip()
            if normalized in VAGUE_LITERALS:
                result.issues.append(ValidationIssue(
                    "VAGUE_LITERAL_NOT_ALLOWED",
                    "Una expresión cualitativa debe registrarse como ambigüedad.",
                    f"{path}.right.value",
                ))

        if not 0.0 <= constraint.confidence <= 1.0:
            result.issues.append(ValidationIssue(
                "INVALID_CONFIDENCE",
                "La confianza debe estar entre 0 y 1.",
                f"{path}.confidence",
            ))
