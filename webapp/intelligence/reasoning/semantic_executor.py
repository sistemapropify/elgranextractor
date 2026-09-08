"""Ejecución controlada del contrato semántico sobre resultados de skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .contracts import SemanticTaskState
from .planner import SemanticExecutionPlan, SemanticPrePlanCritic
from .replanner import SemanticReplanDecision, SemanticReplanner
from .result_critic import SemanticResultCritic, SemanticResultReport


@dataclass
class SemanticRetryResult:
    success: bool
    results: list[dict[str, Any]] = field(default_factory=list)
    inventory_complete: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class SemanticExecutionOutcome:
    status: str
    mode: str
    task_hash: str
    initial_report: SemanticResultReport
    final_report: SemanticResultReport
    decision: SemanticReplanDecision
    final_results: list[dict[str, Any]] = field(default_factory=list)
    attempts_used: int = 0
    authority_applied: bool = False
    signals: list[str] = field(default_factory=list)
    retry_metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def publishable(self) -> bool:
        return self.final_report.publishable

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "task_hash": self.task_hash,
            "publishable": self.publishable,
            "authority_applied": self.authority_applied,
            "attempts_used": self.attempts_used,
            "initial_report": self.initial_report.to_dict(),
            "final_report": self.final_report.to_dict(),
            "decision": self.decision.to_dict(),
            "final_result_count": len(self.final_results),
            "signals": list(self.signals),
            "retry_metadata": dict(self.retry_metadata),
            "error": self.error,
        }


RetryCallback = Callable[
    [SemanticTaskState, SemanticExecutionPlan, SemanticReplanDecision],
    SemanticRetryResult,
]


class SemanticExecutionExecutor:
    """Aplica postfiltro y, como máximo, una recuperación para la misma tarea."""

    MODES = {"shadow", "advisory", "enforced"}
    SAFE_BROAD_PUSHDOWN = {
        "tipo_propiedad", "distrito", "operacion", "condicion", "moneda",
    }

    @classmethod
    def execute(
        cls,
        task: SemanticTaskState,
        initial_results: list[dict[str, Any]] | None,
        *,
        mode: str,
        execution_plan: SemanticExecutionPlan | None = None,
        retry: RetryCallback | None = None,
        attempts_used: int = 0,
    ) -> SemanticExecutionOutcome:
        mode = mode if mode in cls.MODES else "shadow"
        plan = execution_plan or SemanticPrePlanCritic.build(task)
        task_hash = task.fingerprint()
        initial = [item for item in (initial_results or []) if isinstance(item, dict)]
        initial_report = SemanticResultCritic.evaluate(task, initial)
        decision = SemanticReplanner.decide(
            task, plan, initial_report, attempts_used=attempts_used,
        )
        final_results = cls._matching(initial, initial_report)
        initial_status = cls._status_for_report(initial_report)

        if not decision.should_retry or mode == "shadow" or retry is None:
            authority = mode == "enforced" and initial_report.publishable
            signals = list(initial_report.signals) + list(decision.signals)
            if decision.should_retry and mode == "shadow":
                signals.append("SEMANTIC_RETRY_OBSERVED_ONLY")
            if decision.should_retry and retry is None:
                signals.append("SEMANTIC_RETRY_CALLBACK_UNAVAILABLE")
            return SemanticExecutionOutcome(
                status=initial_status, mode=mode, task_hash=task_hash,
                initial_report=initial_report, final_report=initial_report,
                decision=decision, final_results=final_results,
                attempts_used=attempts_used, authority_applied=authority,
                signals=list(dict.fromkeys(signals)),
            )

        try:
            retry_result = retry(task, plan, decision)
        except Exception as exc:
            return SemanticExecutionOutcome(
                status="retry_failed", mode=mode, task_hash=task_hash,
                initial_report=initial_report, final_report=initial_report,
                decision=decision, final_results=final_results,
                attempts_used=attempts_used + 1, authority_applied=False,
                signals=list(dict.fromkeys([
                    *initial_report.signals, *decision.signals,
                    "SEMANTIC_RETRY_EXCEPTION",
                ])),
                error=f"{type(exc).__name__}: {str(exc)[:180]}",
            )

        if task.fingerprint() != task_hash:
            return SemanticExecutionOutcome(
                status="task_changed_during_retry", mode=mode,
                task_hash=task_hash, initial_report=initial_report,
                final_report=initial_report, decision=decision,
                attempts_used=attempts_used + 1, authority_applied=False,
                signals=["SEMANTIC_TASK_HASH_CHANGED"],
                retry_metadata=dict(retry_result.metadata),
                error="La tarea cambió durante el reintento y sus resultados se descartaron.",
            )

        if not retry_result.success:
            return SemanticExecutionOutcome(
                status="retry_failed", mode=mode, task_hash=task_hash,
                initial_report=initial_report, final_report=initial_report,
                decision=decision, final_results=final_results,
                attempts_used=attempts_used + 1, authority_applied=False,
                signals=list(dict.fromkeys([
                    *initial_report.signals, *decision.signals,
                    "SEMANTIC_RETRY_FAILED",
                ])),
                retry_metadata=dict(retry_result.metadata),
                error=retry_result.error,
            )

        retried = [
            item for item in retry_result.results if isinstance(item, dict)
        ]
        final_report = SemanticResultCritic.evaluate(
            task, retried,
            inventory_complete=retry_result.inventory_complete,
        )
        final_decision = SemanticReplanner.decide(
            task, plan, final_report, attempts_used=attempts_used + 1,
        )
        final_results = cls._matching(retried, final_report)
        authority = mode == "enforced" and final_report.publishable
        signals = list(dict.fromkeys([
            *initial_report.signals, *decision.signals,
            *final_report.signals, *final_decision.signals,
        ]))
        return SemanticExecutionOutcome(
            status=cls._status_for_report(final_report),
            mode=mode, task_hash=task_hash,
            initial_report=initial_report, final_report=final_report,
            decision=final_decision, final_results=final_results,
            attempts_used=attempts_used + 1, authority_applied=authority,
            signals=signals, retry_metadata=dict(retry_result.metadata),
        )

    @classmethod
    def broad_retry_params(
        cls, execution_plan: SemanticExecutionPlan,
    ) -> dict[str, Any]:
        """Conserva solo pushdowns categóricos fiables; lo demás se postfiltra."""
        params = {
            key: value
            for key, value in execution_plan.legacy_params.items()
            if key in cls.SAFE_BROAD_PUSHDOWN and value not in (None, "", [])
        }
        params.update({
            "semantic_query": "",
            "top_k": 0,
            "_semantic_inventory_scan": True,
        })
        return params

    @staticmethod
    def _matching(
        results: list[dict[str, Any]], report: SemanticResultReport,
    ) -> list[dict[str, Any]]:
        if not report.matched_indexes:
            return []
        return SemanticResultCritic.matching_results(results, report)

    @staticmethod
    def _status_for_report(report: SemanticResultReport) -> str:
        mapping = {
            "pass": "verified_matches",
            "no_match_verified": "verified_empty",
            "empty_unverified": "unverified_empty",
            "insufficient_evidence": "insufficient_evidence",
            "result_mismatch": "result_mismatch",
        }
        return mapping.get(report.status.value, "unresolved")
