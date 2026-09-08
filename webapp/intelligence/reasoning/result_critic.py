"""Crítico determinista de resultados contra el contrato semántico completo."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from .constraint_engine import EntityEvaluation, SemanticConstraintEngine
from .contracts import SemanticTaskState


class ResultCriticStatus(str, Enum):
    PASS = "pass"
    NO_MATCH_VERIFIED = "no_match_verified"
    EMPTY_UNVERIFIED = "empty_unverified"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    RESULT_MISMATCH = "result_mismatch"


@dataclass
class SemanticResultReport:
    status: ResultCriticStatus
    result_count: int
    matched_count: int
    matched_indexes: list[int] = field(default_factory=list)
    constraint_coverage: list[dict[str, Any]] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def publishable(self) -> bool:
        return self.status in {
            ResultCriticStatus.PASS,
            ResultCriticStatus.NO_MATCH_VERIFIED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "publishable": self.publishable,
            "result_count": self.result_count,
            "matched_count": self.matched_count,
            "matched_indexes": list(self.matched_indexes),
            "constraint_coverage": list(self.constraint_coverage),
            "signals": list(self.signals),
            "reason": self.reason,
        }


class SemanticResultCritic:
    """Comprueba evidencia por campo; una ejecución técnica no equivale a éxito."""

    @classmethod
    def evaluate(
        cls,
        task: SemanticTaskState,
        results: Iterable[dict[str, Any]] | None,
        *,
        inventory_complete: bool = False,
    ) -> SemanticResultReport:
        entities = [item for item in (results or []) if isinstance(item, dict)]
        if not entities:
            if inventory_complete:
                return SemanticResultReport(
                    status=ResultCriticStatus.NO_MATCH_VERIFIED,
                    result_count=0,
                    matched_count=0,
                    reason="La búsqueda exhaustiva no encontró filas compatibles.",
                )
            return SemanticResultReport(
                status=ResultCriticStatus.EMPTY_UNVERIFIED,
                result_count=0,
                matched_count=0,
                signals=["ZERO_RESULTS_REQUIRE_INVENTORY_PROOF"],
                reason=(
                    "La ausencia de filas no demuestra por sí sola que no existan "
                    "propiedades compatibles."
                ),
            )

        evaluations = [
            SemanticConstraintEngine.evaluate(entity, task)
            for entity in entities
        ]
        matched_indexes = [
            index for index, evaluation in enumerate(evaluations)
            if evaluation.matched
        ]
        coverage = cls._coverage(task, evaluations)
        incomplete_required = any(
            item["required"]
            and (item["missing_count"] > 0 or item["invalid_count"] > 0)
            for item in coverage
        )

        if matched_indexes:
            signals = []
            if incomplete_required:
                signals.append("PARTIAL_RESULT_EVIDENCE")
            return SemanticResultReport(
                status=ResultCriticStatus.PASS,
                result_count=len(entities),
                matched_count=len(matched_indexes),
                matched_indexes=matched_indexes,
                constraint_coverage=coverage,
                signals=signals,
                reason="Existen resultados que satisfacen todas las restricciones.",
            )
        if incomplete_required:
            return SemanticResultReport(
                status=ResultCriticStatus.INSUFFICIENT_EVIDENCE,
                result_count=len(entities),
                matched_count=0,
                constraint_coverage=coverage,
                signals=["REQUIRED_RESULT_FIELDS_MISSING"],
                reason=(
                    "No puede confirmarse ausencia de coincidencias porque faltan "
                    "campos obligatorios en parte del inventario recuperado."
                ),
            )
        if inventory_complete:
            return SemanticResultReport(
                status=ResultCriticStatus.NO_MATCH_VERIFIED,
                result_count=len(entities),
                matched_count=0,
                constraint_coverage=coverage,
                reason=(
                    "El inventario exhaustivo fue evaluado y no contiene coincidencias."
                ),
            )
        return SemanticResultReport(
            status=ResultCriticStatus.RESULT_MISMATCH,
            result_count=len(entities),
            matched_count=0,
            constraint_coverage=coverage,
            signals=["RETURNED_RESULTS_VIOLATE_SEMANTIC_CONSTRAINTS"],
            reason=(
                "La ejecución devolvió filas, pero ninguna satisface el contrato "
                "semántico completo."
            ),
        )

    @staticmethod
    def matching_results(
        results: Iterable[dict[str, Any]],
        report: SemanticResultReport,
    ) -> list[dict[str, Any]]:
        entities = [item for item in results if isinstance(item, dict)]
        return [
            entities[index]
            for index in report.matched_indexes
            if 0 <= index < len(entities)
        ]

    @staticmethod
    def _coverage(
        task: SemanticTaskState,
        evaluations: list[EntityEvaluation],
    ) -> list[dict[str, Any]]:
        coverage = []
        for index, constraint in enumerate(task.constraints):
            checks = [
                evaluation.checks[index]
                for evaluation in evaluations
                if index < len(evaluation.checks)
            ]
            coverage.append({
                "constraint_id": constraint.id,
                "required": constraint.required,
                "evaluated_count": sum(
                    1 for item in checks
                    if item.status in {"matched", "not_matched"}
                ),
                "matched_count": sum(1 for item in checks if item.matched),
                "missing_count": sum(
                    1 for item in checks if item.status == "missing_operand"
                ),
                "invalid_count": sum(
                    1 for item in checks if item.status == "invalid_value"
                ),
            })
        return coverage
