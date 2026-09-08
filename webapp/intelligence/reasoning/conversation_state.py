"""Estado conversacional semántico sobre metadata existente, sin tablas nuevas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import (
    SemanticTaskState,
    TaskRelationship,
)
from .validators import SemanticTaskValidator


@dataclass
class StateTransitionResult:
    accepted: bool
    action: str
    task: SemanticTaskState | None
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "action": self.action,
            "task_hash": self.task.fingerprint() if self.task else "",
            "issues": list(self.issues),
        }


class SemanticConversationState:
    """Persiste solo contratos validados en Conversation.metadata."""

    METADATA_KEY = "semantic_reasoning_task_shadow"

    @classmethod
    def load(cls, metadata: dict[str, Any] | None) -> SemanticTaskState | None:
        payload = (metadata or {}).get(cls.METADATA_KEY)
        if not isinstance(payload, dict):
            return None
        try:
            task = SemanticTaskState.from_dict(payload)
        except (TypeError, ValueError):
            return None
        return task if SemanticTaskValidator.validate(task).valid else None

    @classmethod
    def apply(
        cls,
        metadata: dict[str, Any] | None,
        candidate: SemanticTaskState,
    ) -> tuple[dict[str, Any], StateTransitionResult]:
        output = dict(metadata or {})
        previous = cls.load(output)
        result = cls.validate_transition(previous, candidate)
        if not result.accepted:
            return output, result
        if result.action == "clear":
            output.pop(cls.METADATA_KEY, None)
        elif result.action in {"create", "replace", "update"}:
            output[cls.METADATA_KEY] = candidate.to_dict()
        return output, result

    @classmethod
    def validate_transition(
        cls,
        previous: SemanticTaskState | None,
        candidate: SemanticTaskState,
    ) -> StateTransitionResult:
        validation = SemanticTaskValidator.validate(candidate)
        if not validation.valid:
            return StateTransitionResult(
                accepted=False,
                action="reject",
                task=previous,
                issues=[item.code for item in validation.issues],
            )

        relationship = candidate.transition.relationship
        if relationship == TaskRelationship.CANCELLED:
            return StateTransitionResult(True, "clear", None)
        if relationship == TaskRelationship.AMBIGUOUS:
            return StateTransitionResult(
                accepted=False,
                action="keep",
                task=previous,
                issues=["AMBIGUOUS_TASK_RELATIONSHIP"],
            )
        if relationship == TaskRelationship.NEW_TASK:
            return StateTransitionResult(
                accepted=True,
                action="replace" if previous else "create",
                task=candidate,
            )
        if previous is None:
            return StateTransitionResult(
                accepted=False,
                action="reject",
                task=None,
                issues=["MISSING_PREVIOUS_TASK"],
            )
        if (
            previous.objective != candidate.objective
            or previous.entity != candidate.entity
        ):
            return StateTransitionResult(
                accepted=False,
                action="reject",
                task=previous,
                issues=["TASK_IDENTITY_CHANGED_DURING_CONTINUATION"],
            )

        previous_ids = {item.id for item in previous.constraints}
        current_ids = {item.id for item in candidate.constraints}
        carried = set(candidate.transition.carried_constraint_ids)
        added = set(candidate.transition.added_constraint_ids)
        removed = set(candidate.transition.removed_constraint_ids)

        issues = []
        silently_lost = previous_ids - current_ids - removed
        if silently_lost:
            issues.append("PREVIOUS_CONSTRAINT_SILENTLY_LOST")
        undeclared_removal = removed - previous_ids
        if undeclared_removal:
            issues.append("REMOVED_UNKNOWN_PREVIOUS_CONSTRAINT")
        unmarked_carried = (previous_ids & current_ids) - carried
        if unmarked_carried:
            issues.append("CARRIED_CONSTRAINT_NOT_DECLARED")
        unmarked_added = (current_ids - previous_ids) - added
        if unmarked_added:
            issues.append("ADDED_CONSTRAINT_NOT_DECLARED")
        stale_added = added - (current_ids - previous_ids)
        if stale_added:
            issues.append("ADDED_CONSTRAINT_WAS_NOT_NEW")
        stale_carried = carried - (previous_ids & current_ids)
        if stale_carried:
            issues.append("CARRIED_CONSTRAINT_WAS_NOT_PREVIOUS")

        if issues:
            return StateTransitionResult(
                accepted=False,
                action="reject",
                task=previous,
                issues=issues,
            )
        return StateTransitionResult(
            accepted=True,
            action="update",
            task=candidate,
        )
