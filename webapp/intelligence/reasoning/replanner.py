"""Decisiones acotadas de replanificación a partir de evidencia estructurada."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .contracts import SemanticTaskState
from .planner import SemanticExecutionPlan
from .result_critic import ResultCriticStatus, SemanticResultReport


class ReplanAction(str, Enum):
    NONE = "none"
    APPLY_POST_FILTER = "apply_post_filter"
    RETRY_BROAD_INVENTORY = "retry_broad_inventory"
    ENRICH_REQUIRED_FIELDS = "enrich_required_fields"
    STOP = "stop"


@dataclass
class SemanticReplanDecision:
    action: ReplanAction
    should_retry: bool
    task_hash: str
    max_attempts: int = 1
    requested_fields: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "should_retry": self.should_retry,
            "task_hash": self.task_hash,
            "max_attempts": self.max_attempts,
            "requested_fields": list(self.requested_fields),
            "signals": list(self.signals),
            "reason": self.reason,
        }


class SemanticReplanner:
    """No cambia la intención: solo propone una ruta segura para el mismo task hash."""

    MAX_ATTEMPTS = 1

    @classmethod
    def decide(
        cls,
        task: SemanticTaskState,
        execution_plan: SemanticExecutionPlan,
        report: SemanticResultReport,
        *,
        attempts_used: int = 0,
    ) -> SemanticReplanDecision:
        task_hash = task.fingerprint()
        if attempts_used >= cls.MAX_ATTEMPTS:
            return SemanticReplanDecision(
                action=ReplanAction.STOP,
                should_retry=False,
                task_hash=task_hash,
                signals=["SEMANTIC_REPLAN_LIMIT_REACHED"],
                reason="Se alcanzó el máximo de reintentos para la misma tarea.",
            )
        if report.status == ResultCriticStatus.PASS:
            if report.matched_count < report.result_count:
                return SemanticReplanDecision(
                    action=ReplanAction.APPLY_POST_FILTER,
                    should_retry=False,
                    task_hash=task_hash,
                    reason=(
                        "Hay coincidencias verificadas; solo deben publicarse "
                        "los índices aprobados por el motor."
                    ),
                )
            return SemanticReplanDecision(
                action=ReplanAction.NONE,
                should_retry=False,
                task_hash=task_hash,
                reason="Todos los resultados recuperados cumplen el contrato.",
            )
        if report.status == ResultCriticStatus.NO_MATCH_VERIFIED:
            return SemanticReplanDecision(
                action=ReplanAction.NONE,
                should_retry=False,
                task_hash=task_hash,
                reason="La ausencia de coincidencias ya fue verificada.",
            )
        if report.status == ResultCriticStatus.INSUFFICIENT_EVIDENCE:
            missing_fields = cls._missing_fields(task, report)
            return SemanticReplanDecision(
                action=ReplanAction.ENRICH_REQUIRED_FIELDS,
                should_retry=True,
                task_hash=task_hash,
                requested_fields=missing_fields,
                signals=["REPLAN_REQUIRES_FIELD_ENRICHMENT"],
                reason=(
                    "El segundo intento debe recuperar los campos requeridos "
                    "antes de volver a evaluar."
                ),
            )
        if report.status in {
            ResultCriticStatus.EMPTY_UNVERIFIED,
            ResultCriticStatus.RESULT_MISMATCH,
        }:
            return SemanticReplanDecision(
                action=ReplanAction.RETRY_BROAD_INVENTORY,
                should_retry=True,
                task_hash=task_hash,
                requested_fields=list(execution_plan.required_result_fields),
                signals=["REPLAN_REQUIRES_BROAD_RETRIEVAL"],
                reason=(
                    "El segundo intento debe recuperar inventario amplio y aplicar "
                    "el contrato completo fuera del filtro legado."
                ),
            )
        return SemanticReplanDecision(
            action=ReplanAction.STOP,
            should_retry=False,
            task_hash=task_hash,
            signals=["UNKNOWN_RESULT_CRITIC_STATUS"],
            reason="No existe una estrategia segura para este veredicto.",
        )

    @staticmethod
    def _missing_fields(
        task: SemanticTaskState,
        report: SemanticResultReport,
    ) -> list[str]:
        missing_ids = {
            item.get("constraint_id")
            for item in report.constraint_coverage
            if item.get("required")
            and (
                int(item.get("missing_count") or 0) > 0
                or int(item.get("invalid_count") or 0) > 0
            )
        }
        fields = set()
        for constraint in task.constraints:
            if constraint.id not in missing_ids:
                continue
            if constraint.left.kind.value == "field":
                fields.add(str(constraint.left.value))
            if constraint.right.kind.value == "field":
                fields.add(str(constraint.right.value))
        return sorted(fields)
