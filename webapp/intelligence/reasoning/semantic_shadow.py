"""Observación comparativa del razonamiento nuevo frente al SearchPlan vigente."""

from __future__ import annotations

import os
import time
from typing import Any

from .contracts import OperandKind, SemanticTaskState
from .planner import PlanStatus, SemanticPrePlanCritic
from .semantic_compiler import SemanticIntentCompiler


_FIELD_TO_LEGACY = {
    "property_type": "property_type_name",
    "district": "district_name",
    "operation": "operation_type_name",
    "status": "property_status_name",
    "currency": "currency_name",
    "price": "price",
    "bedrooms": "bedrooms",
    "bathrooms": "bathrooms",
    "half_bathrooms": "half_bathrooms",
    "land_area": "land_area",
    "built_area": "built_area",
}


class SemanticReasoningShadow:
    """Compila la intención; la autoridad se decide en el ejecutor de resultados."""

    MODES = {"off", "shadow", "advisory", "enforced"}

    @classmethod
    def mode(cls) -> str:
        value = os.environ.get("SEMANTIC_REASONING_MODE", "off").strip().lower()
        return value if value in cls.MODES else "off"

    @classmethod
    def observe(
        cls,
        *,
        query: str,
        active_task: dict[str, Any] | None,
        search_plan: dict[str, Any] | None,
        conversation_excerpt: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        mode = cls.mode()
        base = {
            "enabled": mode != "off",
            "mode": mode,
            "authority_applied": False,
            "status": "disabled" if mode == "off" else "started",
            "signals": [],
            "metrics": {},
        }
        if mode == "off":
            return base

        started = time.perf_counter()
        try:
            compiled = SemanticIntentCompiler.compile(
                query=query,
                active_task=active_task,
                conversation_excerpt=conversation_excerpt,
            )
        except Exception as exc:
            base.update({
                "status": "failed",
                "reason": f"{type(exc).__name__}: {str(exc)[:180]}",
                "signals": ["SEMANTIC_COMPILER_EXCEPTION"],
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            })
            return base

        base["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
        if not compiled.success or compiled.task is None:
            issue_codes = [item.code for item in compiled.validation.issues]
            base.update({
                "status": compiled.status,
                "reason": compiled.error or "El compilador no produjo una tarea válida.",
                "signals": issue_codes or ["SEMANTIC_COMPILATION_FAILED"],
                "metrics": {
                    "validation_issue_count": len(issue_codes),
                },
            })
            return base

        task = compiled.task
        execution_plan = SemanticPrePlanCritic.build(task)
        coverage = cls.compare_with_search_plan(task, search_plan)
        signals = list(execution_plan.signals)
        if execution_plan.status != PlanStatus.READY:
            signals.append("SEMANTIC_PREPLAN_NOT_READY")
        if coverage["missing_constraints"]:
            signals.append("LEGACY_PLAN_SEMANTIC_GAP")
        if coverage["unsupported_constraints"]:
            signals.append("LEGACY_PLAN_UNSUPPORTED_RELATION")
        if task.ambiguities:
            signals.append("SEMANTIC_AMBIGUITY_PRESENT")

        base.update({
            "status": "completed",
            "confidence": task.confidence,
            "task": task.to_dict(),
            "execution_plan": execution_plan.to_dict(),
            "signals": signals,
            "metrics": {
                "semantic_task_hash": task.fingerprint(),
                "objective": task.objective.value,
                "task_status": task.status.value,
                "constraint_count": len(task.constraints),
                "ambiguity_count": len(task.ambiguities),
                "required_ambiguity_count": sum(
                    1 for item in task.ambiguities if item.required
                ),
                "plan_status": execution_plan.status.value,
                "selected_skill": execution_plan.selected_skill,
                "pushdown_constraint_count": len(
                    execution_plan.pushdown_constraint_ids
                ),
                "post_filter_constraint_count": len(
                    execution_plan.post_filter_constraint_ids
                ),
                **coverage,
            },
        })
        return base

    @classmethod
    def compare_with_search_plan(
        cls,
        task: SemanticTaskState,
        search_plan: dict[str, Any] | None,
    ) -> dict[str, Any]:
        legacy_conditions = list((search_plan or {}).get("conditions") or [])
        legacy_signatures = {
            (
                str(item.get("field_name") or ""),
                str(item.get("operator") or ""),
                cls._stable_value(item.get("value")),
            )
            for item in legacy_conditions
        }
        represented: list[str] = []
        missing: list[str] = []
        unsupported: list[str] = []
        matched_legacy: set[tuple[Any, ...]] = set()

        for constraint in task.constraints:
            left = constraint.left
            right = constraint.right
            if left.kind != OperandKind.FIELD:
                unsupported.append(constraint.id)
                continue
            legacy_field = _FIELD_TO_LEGACY.get(str(left.value))
            if not legacy_field:
                unsupported.append(constraint.id)
                continue
            if right.kind == OperandKind.FIELD:
                unsupported.append(constraint.id)
                continue
            if right.kind not in {OperandKind.LITERAL, OperandKind.SET}:
                unsupported.append(constraint.id)
                continue

            signature = (
                legacy_field,
                constraint.operator.value,
                cls._stable_value(right.value),
            )
            if signature in legacy_signatures:
                represented.append(constraint.id)
                matched_legacy.add(signature)
            else:
                missing.append(constraint.id)

        return {
            "represented_constraint_count": len(represented),
            "missing_constraint_count": len(missing),
            "unsupported_constraint_count": len(unsupported),
            "legacy_only_constraint_count": max(
                0, len(legacy_signatures - matched_legacy)
            ),
            "represented_constraints": represented,
            "missing_constraints": missing,
            "unsupported_constraints": unsupported,
        }

    @staticmethod
    def event_payload(observation: dict[str, Any], search_plan_hash: str = "") -> dict:
        """Reduce la observación a claves permitidas por la telemetría."""
        return {
            "status": observation.get("status"),
            "mode": observation.get("mode"),
            "confidence": observation.get("confidence"),
            "authority_applied": False,
            "reason": observation.get("reason", ""),
            "signals": observation.get("signals") or [],
            "metrics": observation.get("metrics") or {},
            "latency_ms": observation.get("latency_ms"),
            "search_plan_hash": search_plan_hash,
        }

    @staticmethod
    def _stable_value(value: Any) -> Any:
        if isinstance(value, list):
            return tuple(SemanticReasoningShadow._stable_value(item) for item in value)
        if isinstance(value, dict):
            return tuple(
                sorted(
                    (str(key), SemanticReasoningShadow._stable_value(item))
                    for key, item in value.items()
                )
            )
        try:
            return float(value) if hasattr(value, "as_integer_ratio") else value
        except (TypeError, ValueError):
            return value
