"""Representación intermedia general para tareas agentic.

El contrato describe lo que pidió el usuario sin acoplarlo a una skill, consulta
SQL o colección concreta. Las herramientas reciben una compilación posterior de
este estado; nunca el texto libre producido por un modelo.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any


class TaskObjective(str, Enum):
    SEARCH_PROPERTIES = "search_properties"
    PROPERTY_DETAIL = "property_detail"
    COMPARE_PROPERTIES = "compare_properties"
    ANALYZE_MARKET = "analyze_market"
    OTHER = "other"


class TaskStatus(str, Enum):
    PLANNING = "planning"
    NEEDS_CLARIFICATION = "needs_clarification"
    READY = "ready"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    REPLANNING = "replanning"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"

class TaskRelationship(str, Enum):
    NEW_TASK = "new_task"
    CONTINUATION = "continuation"
    CORRECTION = "correction"
    CANCELLED = "cancelled"
    AMBIGUOUS = "ambiguous"



class OperandKind(str, Enum):
    FIELD = "field"
    LITERAL = "literal"
    SET = "set"


class ConstraintOperator(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    BETWEEN = "between"


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return list(value)
    return value


@dataclass(frozen=True)
class SemanticOperand:
    kind: OperandKind
    value: Any
    unit: str | None = None

    @classmethod
    def field(cls, name: str) -> "SemanticOperand":
        return cls(kind=OperandKind.FIELD, value=name)

    @classmethod
    def literal(cls, value: Any, unit: str | None = None) -> "SemanticOperand":
        return cls(kind=OperandKind.LITERAL, value=value, unit=unit)

    @classmethod
    def values(cls, values: list[Any]) -> "SemanticOperand":
        return cls(kind=OperandKind.SET, value=list(values))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "value": _json_safe(self.value),
            "unit": self.unit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SemanticOperand":
        return cls(
            kind=OperandKind(str(data.get("kind"))),
            value=data.get("value"),
            unit=data.get("unit"),
        )


@dataclass(frozen=True)
class SemanticConstraint:
    id: str
    left: SemanticOperand
    operator: ConstraintOperator
    right: SemanticOperand
    required: bool = True
    confidence: float = 1.0
    source_text: str = ""
    source_turn: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "left": self.left.to_dict(),
            "operator": self.operator.value,
            "right": self.right.to_dict(),
            "required": self.required,
            "confidence": self.confidence,
            "source_text": self.source_text,
            "source_turn": self.source_turn,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SemanticConstraint":
        return cls(
            id=str(data.get("id") or ""),
            left=SemanticOperand.from_dict(data.get("left") or {}),
            operator=ConstraintOperator(str(data.get("operator"))),
            right=SemanticOperand.from_dict(data.get("right") or {}),
            required=bool(data.get("required", True)),
            confidence=float(data.get("confidence", 1.0)),
            source_text=str(data.get("source_text") or ""),
            source_turn=int(data.get("source_turn") or 0),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class SemanticAmbiguity:
    id: str
    concept: str
    source_text: str
    reason: str
    clarification: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SemanticAmbiguity":
        return cls(
            id=str(data.get("id") or ""),
            concept=str(data.get("concept") or ""),
            source_text=str(data.get("source_text") or ""),
            reason=str(data.get("reason") or ""),
            clarification=str(data.get("clarification") or ""),
            required=bool(data.get("required", True)),
        )


@dataclass(frozen=True)
class SemanticPreference:
    id: str
    concept: str
    value: Any
    weight: float = 0.5
    source_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SemanticPreference":
        return cls(
            id=str(data.get("id") or ""),
            concept=str(data.get("concept") or ""),
            value=data.get("value"),
            weight=float(data.get("weight", 0.5)),
            source_text=str(data.get("source_text") or ""),
        )


@dataclass(frozen=True)
class TaskTransition:
    relationship: TaskRelationship = TaskRelationship.NEW_TASK
    carried_constraint_ids: list[str] = field(default_factory=list)
    added_constraint_ids: list[str] = field(default_factory=list)
    removed_constraint_ids: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "relationship": self.relationship.value,
            "carried_constraint_ids": list(self.carried_constraint_ids),
            "added_constraint_ids": list(self.added_constraint_ids),
            "removed_constraint_ids": list(self.removed_constraint_ids),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TaskTransition":
        payload = data or {}
        return cls(
            relationship=TaskRelationship(
                str(payload.get("relationship") or "new_task")
            ),
            carried_constraint_ids=[
                str(item)
                for item in (payload.get("carried_constraint_ids") or [])
            ],
            added_constraint_ids=[
                str(item)
                for item in (payload.get("added_constraint_ids") or [])
            ],
            removed_constraint_ids=[
                str(item)
                for item in (payload.get("removed_constraint_ids") or [])
            ],
            reason=str(payload.get("reason") or ""),
        )



@dataclass
class SemanticTaskState:
    objective: TaskObjective
    entity: str
    original_query: str
    effective_query: str = ""
    transition: TaskTransition = field(default_factory=TaskTransition)
    constraints: list[SemanticConstraint] = field(default_factory=list)
    preferences: list[SemanticPreference] = field(default_factory=list)
    ambiguities: list[SemanticAmbiguity] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PLANNING
    confidence: float = 0.0
    schema_version: str = "2"

    @property
    def has_required_ambiguities(self) -> bool:
        return any(item.required for item in self.ambiguities)

    def refresh_status(self) -> TaskStatus:
        if self.has_required_ambiguities:
            self.status = TaskStatus.NEEDS_CLARIFICATION
        elif self.status in {TaskStatus.PLANNING, TaskStatus.NEEDS_CLARIFICATION}:
            self.status = TaskStatus.READY
        return self.status

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective.value,
            "entity": self.entity,
            "original_query": self.original_query,
            "effective_query": self.effective_query or self.original_query,
            "transition": self.transition.to_dict(),
            "constraints": [item.to_dict() for item in self.constraints],
            "preferences": [item.to_dict() for item in self.preferences],
            "ambiguities": [item.to_dict() for item in self.ambiguities],
            "assumptions": list(self.assumptions),
            "evidence": list(self.evidence),
            "attempts": list(self.attempts),
            "status": self.status.value,
            "confidence": self.confidence,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SemanticTaskState":
        return cls(
            objective=TaskObjective(str(data.get("objective") or "other")),
            entity=str(data.get("entity") or ""),
            original_query=str(data.get("original_query") or ""),
            effective_query=str(data.get("effective_query") or ""),
            transition=TaskTransition.from_dict(data.get("transition")),
            constraints=[
                SemanticConstraint.from_dict(item)
                for item in (data.get("constraints") or [])
            ],
            preferences=[
                SemanticPreference.from_dict(item)
                for item in (data.get("preferences") or [])
            ],
            ambiguities=[
                SemanticAmbiguity.from_dict(item)
                for item in (data.get("ambiguities") or [])
            ],
            assumptions=[str(item) for item in (data.get("assumptions") or [])],
            evidence=list(data.get("evidence") or []),
            attempts=list(data.get("attempts") or []),
            status=TaskStatus(str(data.get("status") or "planning")),
            confidence=float(data.get("confidence") or 0.0),
            schema_version=str(data.get("schema_version") or "2"),
        )

    def fingerprint(self) -> str:
        payload = self.to_dict()
        payload.pop("evidence", None)
        payload.pop("attempts", None)
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
