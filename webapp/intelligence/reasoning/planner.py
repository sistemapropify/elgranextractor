"""Planificador y crítico previo basados en capacidades, no en frases."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .contracts import (
    ConstraintOperator,
    OperandKind,
    SemanticTaskState,
    TaskObjective,
    TaskRelationship,
)
from .validators import PROPERTY_FIELDS, SemanticTaskValidator


class PlanStatus(str, Enum):
    READY = "ready"
    CLARIFY = "clarify"
    NO_ACTION = "no_action"
    UNSUPPORTED = "unsupported"
    INVALID = "invalid"


@dataclass
class SemanticExecutionPlan:
    status: PlanStatus
    selected_skill: str = ""
    legacy_params: dict[str, Any] = field(default_factory=dict)
    pushdown_constraint_ids: list[str] = field(default_factory=list)
    post_filter_constraint_ids: list[str] = field(default_factory=list)
    required_result_fields: list[str] = field(default_factory=list)
    clarification_questions: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    reason: str = ""
    fetch_limit: int = 9999

    @property
    def executable(self) -> bool:
        return self.status == PlanStatus.READY and bool(self.selected_skill)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "executable": self.executable,
            "selected_skill": self.selected_skill,
            "legacy_params": dict(self.legacy_params),
            "pushdown_constraint_ids": list(self.pushdown_constraint_ids),
            "post_filter_constraint_ids": list(self.post_filter_constraint_ids),
            "required_result_fields": list(self.required_result_fields),
            "clarification_questions": list(self.clarification_questions),
            "signals": list(self.signals),
            "reason": self.reason,
            "fetch_limit": self.fetch_limit,
        }


_PUSH_DOWN = {
    ("property_type", ConstraintOperator.EQ): "tipo_propiedad",
    ("district", ConstraintOperator.EQ): "distrito",
    ("operation", ConstraintOperator.EQ): "operacion",
    ("status", ConstraintOperator.EQ): "condicion",
    ("currency", ConstraintOperator.EQ): "moneda",
    ("price", ConstraintOperator.EQ): "precio",
    ("price", ConstraintOperator.GTE): "precio_min",
    ("price", ConstraintOperator.LTE): "precio_max",
    ("bedrooms", ConstraintOperator.EQ): "habitaciones",
    ("bedrooms", ConstraintOperator.GTE): "habitaciones_min",
    ("bathrooms", ConstraintOperator.EQ): "banos",
    ("bathrooms", ConstraintOperator.GTE): "banos_min",
    ("built_area", ConstraintOperator.GTE): "area_min",
    ("built_area", ConstraintOperator.LTE): "area_max",
}


class SemanticPrePlanCritic:
    """Construye un plan verificable desde el contrato ya validado."""

    @classmethod
    def build(cls, task: SemanticTaskState) -> SemanticExecutionPlan:
        validation = SemanticTaskValidator.validate(task)
        if not validation.valid:
            return SemanticExecutionPlan(
                status=PlanStatus.INVALID,
                signals=[item.code for item in validation.issues],
                reason="El contrato semántico no superó validación.",
            )
        if task.transition.relationship == TaskRelationship.CANCELLED:
            return SemanticExecutionPlan(
                status=PlanStatus.NO_ACTION,
                reason="La tarea fue cancelada por el usuario.",
            )
        if task.transition.relationship == TaskRelationship.AMBIGUOUS:
            return SemanticExecutionPlan(
                status=PlanStatus.CLARIFY,
                signals=["AMBIGUOUS_TASK_RELATIONSHIP"],
                reason="No se pudo determinar si el turno continúa la tarea activa.",
            )
        required_ambiguities = [
            item for item in task.ambiguities if item.required
        ]
        if required_ambiguities:
            return SemanticExecutionPlan(
                status=PlanStatus.CLARIFY,
                clarification_questions=[
                    item.clarification for item in required_ambiguities
                    if item.clarification.strip()
                ],
                signals=["REQUIRED_SEMANTIC_AMBIGUITY"],
                reason="Faltan criterios que no pueden asumirse con seguridad.",
            )
        if task.objective != TaskObjective.SEARCH_PROPERTIES:
            return SemanticExecutionPlan(
                status=PlanStatus.UNSUPPORTED,
                signals=["OBJECTIVE_NOT_YET_SUPPORTED_BY_V2_PLANNER"],
                reason=(
                    "La primera versión del planificador solo observa búsquedas "
                    "de inventario inmobiliario."
                ),
            )

        legacy_params: dict[str, Any] = {}
        pushdown = []
        post_filter = []
        required_fields = set()
        signals = []

        for constraint in task.constraints:
            left_field = (
                str(constraint.left.value)
                if constraint.left.kind == OperandKind.FIELD
                else ""
            )
            if left_field:
                required_fields.add(left_field)
            if constraint.right.kind == OperandKind.FIELD:
                required_fields.add(str(constraint.right.value))

            legacy_name = _PUSH_DOWN.get((left_field, constraint.operator))
            can_push = (
                legacy_name is not None
                and constraint.right.kind == OperandKind.LITERAL
            )
            if can_push:
                legacy_params[legacy_name] = constraint.right.value
                pushdown.append(constraint.id)
            else:
                post_filter.append(constraint.id)

        if post_filter:
            signals.append("SEMANTIC_POST_FILTER_REQUIRED")
        if any(
            constraint.left.value == "land_area"
            for constraint in task.constraints
            if constraint.left.kind == OperandKind.FIELD
        ):
            signals.append("LAND_AREA_MUST_NOT_MAP_TO_BUILT_AREA")

        return SemanticExecutionPlan(
            status=PlanStatus.READY,
            selected_skill="busqueda_propiedades",
            legacy_params=legacy_params,
            pushdown_constraint_ids=pushdown,
            post_filter_constraint_ids=post_filter,
            required_result_fields=sorted(
                field for field in required_fields if field in PROPERTY_FIELDS
            ),
            signals=signals,
            reason="Todas las restricciones tienen una ruta de ejecución verificable.",
        )
