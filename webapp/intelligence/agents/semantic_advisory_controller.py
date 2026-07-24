"""Autoridad limitada para recomendaciones del juez semántico (Nivel 3A)."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


class SemanticAdvisoryController:
    """Convierte un veredicto LLM en una acción acotada y auditable."""

    ALLOWED_ACTIONS = {"clarify", "block", "replan"}
    HIGH_RISK_SIGNALS = {
        "FILTER_MISMATCH",
        "TYPE_MISMATCH",
        "UNAVAILABLE_PROPERTY",
        "UNSUPPORTED_SUITABILITY",
        "UNGROUNDED_RESULTS",
        "CONTRADICTS_QUERY",
    }

    @classmethod
    def confidence_threshold(cls) -> float:
        try:
            return max(
                0.8,
                min(0.99, float(os.environ.get("EXECUTION_JUDGE_MIN_CONFIDENCE", "0.90"))),
            )
        except (TypeError, ValueError):
            return 0.90

    @classmethod
    def decide(
        cls,
        *,
        semantic_evaluation: Dict[str, Any],
        deterministic_evaluation: Dict[str, Any],
        search_plan: Optional[Dict[str, Any]],
        retries_used: int,
    ) -> Dict[str, Any]:
        mode = semantic_evaluation.get("mode")
        base = {
            "enabled": mode in {"advisory", "enforced"},
            "mode": mode,
            "judge_status": semantic_evaluation.get("status"),
            "judge_verdict": semantic_evaluation.get("verdict"),
            "judge_confidence": semantic_evaluation.get("confidence"),
            "judge_attempts": semantic_evaluation.get("attempts", 0),
            "action": "none",
            "authority_applied": False,
            "reason": "",
            "retries_used": retries_used,
        }
        if not base["enabled"]:
            base["reason"] = "El juez no está en modo advisory."
            return base
        if semantic_evaluation.get("status") != "completed":
            attempts = semantic_evaluation.get("attempts", 0)
            error = semantic_evaluation.get("error") or "evaluación inválida"
            base["reason"] = (
                f"El juez falló de forma segura después de {attempts} "
                f"intento(s): {error}."
            )
            return base

        verdict = semantic_evaluation.get("verdict")
        confidence = float(semantic_evaluation.get("confidence") or 0)
        if verdict not in cls.ALLOWED_ACTIONS:
            if verdict == "pass":
                base["reason"] = (
                    "El juez aprobó la coherencia semántica; no requiere intervención."
                )
            else:
                base["reason"] = "El veredicto no requiere una acción autorizada."
            return base
        if confidence < cls.confidence_threshold():
            base["reason"] = "Confianza inferior al umbral de autoridad."
            return base

        if verdict == "clarify":
            missing = semantic_evaluation.get("missing_information") or []
            if not missing:
                base["reason"] = "No hay información faltante estructurada."
                return base
            base.update({
                "action": "clarify",
                "authority_applied": True,
                "reason": semantic_evaluation.get("reason", ""),
                "clarification_question": cls._clarification_question(missing),
            })
            return base

        if verdict == "replan":
            if retries_used >= 1 or not search_plan:
                base["reason"] = "No hay presupuesto de reintento o plan canónico."
                return base
            # No acepta filtros inventados por el LLM: sólo permite repetir el
            # plan canónico ya normalizado a partir del mensaje del usuario.
            base.update({
                "action": "replan",
                "authority_applied": True,
                "reason": semantic_evaluation.get("reason", ""),
                "suggested_plan": search_plan,
            })
            return base

        signals = {
            str(signal).upper()
            for signal in (semantic_evaluation.get("signals") or [])
        }
        if verdict == "block" and signals & cls.HIGH_RISK_SIGNALS:
            base.update({
                "action": "block",
                "authority_applied": True,
                "reason": semantic_evaluation.get("reason", ""),
            })
            return base

        base["reason"] = "El bloqueo no contiene una señal de riesgo permitida."
        return base

    @staticmethod
    def _clarification_question(missing: list[Any]) -> str:
        values = ", ".join(str(value)[:80] for value in missing[:5])
        return (
            f"Antes de continuar necesito precisar: {values}. "
            "¿Puedes proporcionar esos datos?"
        )
