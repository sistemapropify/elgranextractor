"""Evaluación previa a respuesta para el ciclo agentic de PIL."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Dict, List, Optional


SUITABILITY_TERMS = (
    "ideal para", "adecuad", "apta para", "apto para", "recomend",
    "donde poner", "donde pueda poner", "para construir", "para instalar",
)

USE_CASE_TERMS = (
    "colegio", "clínica", "clinica", "tienda", "negocio", "restaurante",
    "hotel", "almacén", "almacen", "fábrica", "fabrica", "inversión",
    "inversion",
)

EXPLICIT_TYPES = {
    "terreno": "Terreno",
    "departamento": "Departamento",
    "duplex": "Duplex",
    "dúplex": "Duplex",
    "casa": "Casa",
    "local": "Local Comercial",
    "oficina": "Oficina",
}


@dataclass
class EvaluationResult:
    verdict: str
    confidence: float
    reason: str
    signals: List[str] = field(default_factory=list)
    clarification_question: Optional[str] = None
    suggested_plan: Optional[Dict[str, Any]] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExecutionEvaluator:
    """Guardrail determinista; no usa LLM ni modifica estado externo."""

    MAX_BROAD_RESULTS = 50

    @classmethod
    def evaluate(
        cls,
        *,
        message: str,
        results: Dict[str, Any],
        search_plan: Optional[Dict[str, Any]] = None,
        attempt: int = 0,
    ) -> EvaluationResult:
        normalized_message = cls._normalize(message)
        successful = [
            result for result in results.values()
            if isinstance(result, dict) and result.get("success")
        ]
        items = cls._extract_items(successful)
        requirements = [
            requirement
            for result in successful
            for requirement in (result.get("requirements") or [])
        ]
        metrics = {
            "result_count": len(items),
            "successful_agents": len(successful),
            "requirements_total": len(requirements),
            "requirements_satisfied": sum(
                1 for requirement in requirements if requirement.get("satisfied")
            ),
            "attempt": attempt,
        }

        suitability = (
            any(term in normalized_message for term in SUITABILITY_TERMS)
            and any(term in normalized_message for term in USE_CASE_TERMS)
        )
        if suitability:
            has_district = cls._plan_value(search_plan, "distrito") is not None
            has_area = cls._plan_value(search_plan, "area_min") is not None
            has_capacity = bool(re.search(r"\b\d+\s+(?:alumnos?|personas?)\b", normalized_message))
            if not successful and has_district and has_area and has_capacity:
                return EvaluationResult(
                    verdict="pass",
                    confidence=0.97,
                    reason="Hay criterios mínimos para buscar candidatos; la aptitud legal seguirá sin confirmarse.",
                    signals=["SUITABILITY_CANDIDATE_SEARCH"],
                    metrics=metrics,
                )
            if successful and has_district and has_area and has_capacity:
                mismatches = cls._filter_mismatches(items, search_plan)
                if mismatches:
                    return EvaluationResult(
                        verdict="block",
                        confidence=0.99,
                        reason=(
                            f"{len(mismatches)} resultados incumplen distrito, tipo "
                            "o área mínima del plan de búsqueda."
                        ),
                        signals=["SEARCH_PLAN_FILTER_MISMATCH"],
                        metrics={**metrics, "mismatch_count": len(mismatches)},
                    )
                return EvaluationResult(
                    verdict="pass",
                    confidence=0.95,
                    reason=(
                        "Los resultados cumplen los criterios verificables de candidatos; "
                        "no se confirma zonificación ni aptitud legal."
                    ),
                    signals=["CANDIDATES_ONLY", "ZONING_NOT_VERIFIED"],
                    metrics=metrics,
                )
            return EvaluationResult(
                verdict="clarify",
                confidence=0.98,
                reason=(
                    "La consulta solicita aptitud para un uso específico, pero "
                    "la búsqueda de inventario no demuestra aptitud física, legal "
                    "ni comercial."
                ),
                signals=[
                    "SPECIALIZED_SUITABILITY_REQUIRED",
                    "SEMANTIC_RESULTS_NOT_EVIDENCE",
                ] + (["BROAD_RESULT_SET"] if len(items) > cls.MAX_BROAD_RESULTS else []),
                clarification_question=cls._suitability_question(normalized_message),
                metrics=metrics,
            )

        if not successful:
            return EvaluationResult(
                verdict="block",
                confidence=1.0,
                reason="Ningún agente produjo un resultado utilizable.",
                signals=["NO_SUCCESSFUL_AGENT"],
                metrics=metrics,
            )

        unsatisfied_requirements = [
            requirement
            for requirement in requirements
            if not requirement.get("satisfied")
        ]
        if unsatisfied_requirements:
            if attempt < 1:
                return EvaluationResult(
                    verdict="replan",
                    confidence=0.98,
                    reason=(
                        f"Quedaron {len(unsatisfied_requirements)} requisitos "
                        "sin evidencia de ejecución."
                    ),
                    signals=["UNSATISFIED_QUERY_REQUIREMENTS"],
                    suggested_plan=dict(search_plan or {}),
                    metrics={
                        **metrics,
                        "unsatisfied_requirements": len(unsatisfied_requirements),
                    },
                )
            return EvaluationResult(
                verdict="block",
                confidence=0.99,
                reason="El reintento terminó con requisitos todavía no verificados.",
                signals=["REPLAN_DID_NOT_SATISFY_REQUIREMENTS"],
                metrics={
                    **metrics,
                    "unsatisfied_requirements": len(unsatisfied_requirements),
                },
            )

        explicit_type = next(
            (value for keyword, value in EXPLICIT_TYPES.items()
             if re.search(rf"\b{re.escape(keyword)}s?\b", normalized_message)),
            None,
        )
        if explicit_type and items:
            mismatches = [
                item for item in items
                if cls._property_type(item)
                and explicit_type.casefold() not in cls._property_type(item).casefold()
            ]
            if mismatches:
                if attempt < 1:
                    return EvaluationResult(
                        verdict="replan",
                        confidence=0.96,
                        reason=(
                            f"{len(mismatches)} resultados no cumplen el tipo "
                            f"explícito {explicit_type}."
                        ),
                        signals=["EXPLICIT_PROPERTY_TYPE_MISMATCH"],
                        suggested_plan=cls._plan_with_property_type(
                            search_plan, explicit_type
                        ),
                        metrics={**metrics, "mismatch_count": len(mismatches)},
                    )
                return EvaluationResult(
                    verdict="block",
                    confidence=0.98,
                    reason="El reintento todavía contiene tipos incompatibles.",
                    signals=["REPLAN_DID_NOT_FIX_TYPE_MISMATCH"],
                    metrics={**metrics, "mismatch_count": len(mismatches)},
                )

        plan_mismatches = cls._filter_mismatches(items, search_plan)
        if items and plan_mismatches:
            if attempt < 1:
                return EvaluationResult(
                    verdict="replan",
                    confidence=0.98,
                    reason=(
                        f"{len(plan_mismatches)} resultados incumplen uno o más "
                        "filtros obligatorios del plan de búsqueda."
                    ),
                    signals=["SEARCH_PLAN_FILTER_MISMATCH"],
                    suggested_plan=dict(search_plan or {}),
                    metrics={**metrics, "mismatch_count": len(plan_mismatches)},
                )
            return EvaluationResult(
                verdict="block",
                confidence=0.99,
                reason="El reintento todavía incumple filtros obligatorios.",
                signals=["REPLAN_DID_NOT_FIX_FILTER_MISMATCH"],
                metrics={**metrics, "mismatch_count": len(plan_mismatches)},
            )

        if len(items) > cls.MAX_BROAD_RESULTS:
            return EvaluationResult(
                verdict="clarify",
                confidence=0.92,
                reason="La consulta produjo un conjunto demasiado amplio sin evidencia de selección.",
                signals=["BROAD_RESULT_SET", "LOW_SELECTIVITY"],
                clarification_question=(
                    "Encontré demasiadas opciones para darte una recomendación útil. "
                    "¿En qué distrito, rango de precio y tipo de propiedad deseas que busque?"
                ),
                metrics=metrics,
            )

        return EvaluationResult(
            verdict="pass",
            confidence=0.9,
            reason="La ejecución supera los controles deterministas disponibles.",
            signals=[],
            metrics=metrics,
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join((value or "").casefold().split())

    @staticmethod
    def _extract_items(successful: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for result in successful:
            answer = result.get("final_answer")
            if isinstance(answer, list):
                items.extend(item for item in answer if isinstance(item, dict))
            elif isinstance(answer, dict):
                for key in ("resultados", "properties", "propiedades", "data", "items"):
                    value = answer.get(key)
                    if isinstance(value, list):
                        items.extend(item for item in value if isinstance(item, dict))
                        break
        return items

    @staticmethod
    def _property_type(item: Dict[str, Any]) -> str:
        fields = item.get("field_values")
        if not isinstance(fields, dict):
            fields = item
        return str(
            fields.get("property_type_name")
            or fields.get("tipo_propiedad")
            or ""
        )

    @staticmethod
    def _plan_value(plan: Optional[Dict[str, Any]], logical_name: str) -> Any:
        for condition in (plan or {}).get("conditions") or []:
            if condition.get("logical_name") == logical_name:
                return condition.get("value")
        return None

    @classmethod
    def _filter_mismatches(
        cls, items: List[Dict[str, Any]], plan: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        district = cls._plan_value(plan, "distrito")
        property_type = cls._plan_value(plan, "tipo_propiedad")
        area_min = cls._plan_value(plan, "area_min")
        area_max = cls._plan_value(plan, "area_max")
        bedrooms = cls._plan_value(plan, "habitaciones")
        price_min = cls._plan_value(plan, "precio_min")
        price_max = cls._plan_value(plan, "precio_max")
        status = cls._plan_value(plan, "condicion")
        mismatches = []
        for item in items:
            fields = item.get("field_values")
            if not isinstance(fields, dict):
                fields = item
            item_district = fields.get("district_name") or fields.get("distrito")
            item_type = fields.get("property_type_name") or fields.get("tipo_propiedad")
            item_area = (
                fields.get("land_area")
                or fields.get("built_area")
                or fields.get("area_terreno")
                or fields.get("area_construida")
            )
            item_status = (
                fields.get("property_status_name")
                or fields.get("estado")
                or fields.get("status")
            )
            item_bedrooms = (
                fields.get("bedrooms")
                or fields.get("habitaciones")
                or fields.get("dormitorios")
            )
            item_price = fields.get("price") or fields.get("precio")
            invalid = (
                (district and str(item_district or "").casefold() != str(district).casefold())
                or (property_type and str(property_type).casefold() not in str(item_type or "").casefold())
                or (status and str(item_status or "").casefold() != str(status).casefold())
            )
            if area_min is not None:
                try:
                    invalid = invalid or item_area is None or float(item_area) < float(area_min)
                except (TypeError, ValueError):
                    invalid = True
            if area_max is not None:
                try:
                    invalid = invalid or item_area is None or float(item_area) > float(area_max)
                except (TypeError, ValueError):
                    invalid = True
            for actual, expected, comparison in (
                (item_bedrooms, bedrooms, "minimum"),
                (item_price, price_min, "minimum"),
                (item_price, price_max, "maximum"),
            ):
                if expected is None:
                    continue
                try:
                    if comparison == "minimum":
                        invalid = invalid or actual is None or float(actual) < float(expected)
                    else:
                        invalid = invalid or actual is None or float(actual) > float(expected)
                except (TypeError, ValueError):
                    invalid = True
            if invalid:
                mismatches.append(item)
        return mismatches

    @staticmethod
    def _suitability_question(message: str) -> str:
        if "colegio" in message:
            return (
                "Para buscar candidatos reales para un colegio necesito el distrito "
                "o zona, presupuesto, área mínima aproximada y cantidad de alumnos. "
                "La compatibilidad de zonificación deberá validarse por separado. "
                "¿Qué criterios deseas usar?"
            )
        return (
            "Para evaluar esa aptitud necesito distrito o zona, presupuesto, "
            "área mínima y las condiciones indispensables del uso. "
            "¿Qué criterios deseas aplicar?"
        )

    @staticmethod
    def _plan_with_property_type(
        plan: Optional[Dict[str, Any]], property_type: str
    ) -> Dict[str, Any]:
        revised = dict(plan or {})
        conditions = [
            condition for condition in (revised.get("conditions") or [])
            if condition.get("logical_name") != "tipo_propiedad"
        ]
        conditions.append({
            "logical_name": "tipo_propiedad",
            "field_name": "property_type_name",
            "operator": "eq",
            "value": property_type,
            "value_type": "string",
            "required": True,
            "source": "execution_evaluator",
            "currency": None,
        })
        revised["conditions"] = conditions
        revised["top_k"] = min(int(revised.get("top_k", 50)), 50)
        revised.setdefault("query", "")
        revised.setdefault("collections", ["propiedadespropify"])
        revised.setdefault("semantic_query", "")
        revised.setdefault("schema_version", "1")
        return revised
