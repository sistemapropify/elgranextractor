"""Estado efímero y estructurado de una tarea conversacional pendiente."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Dict, Optional, Tuple

from ..search.normalizer import SearchPlanNormalizer


SCHOOL_TERMS = ("colegio", "escuela", "institución educativa", "institucion educativa")
SCHOOL_PURPOSE_TERMS = ("construir", "instalar", "implementar", "poner", "ideal")


class ConversationTaskState:
    """Distingue continuación de consulta nueva sin usar memoria personal."""

    METADATA_KEY = "pending_agent_task"
    LEGACY_KEY = "pending_agent_clarification"

    @classmethod
    def resolve(
        cls, metadata: Optional[Dict[str, Any]], message: str
    ) -> Tuple[str, Optional[Dict[str, Any]], str]:
        metadata = metadata or {}
        pending = metadata.get(cls.METADATA_KEY)
        if not isinstance(pending, dict):
            legacy = metadata.get(cls.LEGACY_KEY)
            if isinstance(legacy, dict):
                pending = cls.from_message(legacy.get("original_message", ""))
        if not pending:
            return message, None, "new_task"

        relationship = cls.relationship(pending, message)
        if relationship == "new_task":
            return message, None, relationship
        if relationship == "ambiguous":
            return message, pending, relationship

        updated = cls.merge(pending, message)
        effective = cls.effective_message(updated, message)
        return effective, updated, "continuation"

    @classmethod
    def from_message(cls, message: str) -> Optional[Dict[str, Any]]:
        normalized = (message or "").casefold()
        if not (
            any(term in normalized for term in SCHOOL_TERMS)
            and any(term in normalized for term in SCHOOL_PURPOSE_TERMS)
        ):
            return None
        task = {
            "schema_version": 1,
            "intent": "school_site_search",
            "purpose": "construir_colegio",
            "status": "collecting_requirements",
            "original_message": message,
            "required_fields": ["distrito", "area_min", "cantidad_alumnos"],
            "optional_fields": ["presupuesto_max"],
            "collected_fields": {},
        }
        return cls.merge(task, message)

    @classmethod
    def merge(cls, task: Dict[str, Any], message: str) -> Dict[str, Any]:
        updated = deepcopy(task)
        collected = dict(updated.get("collected_fields") or {})
        extracted = SearchPlanNormalizer.params_from_message(message)
        mappings = {
            "distrito": "distrito",
            "area_min": "area_min",
            "precio_max": "presupuesto_max",
        }
        for source, target in mappings.items():
            if extracted.get(source) is not None:
                collected[target] = cls._json_value(extracted[source])

        students = re.search(
            r"\b(\d[\d.,]*)\s*(?:alumnos?|estudiantes?|personas?)\b",
            (message or "").casefold(),
        )
        if students:
            collected["cantidad_alumnos"] = int(
                SearchPlanNormalizer._parse_number(students.group(1))
            )

        updated["collected_fields"] = collected
        missing = [
            field for field in updated.get("required_fields", [])
            if collected.get(field) in (None, "")
        ]
        updated["missing_fields"] = missing
        updated["status"] = "collecting_requirements" if missing else "ready"
        return updated

    @classmethod
    def relationship(cls, task: Dict[str, Any], message: str) -> str:
        lowered = (message or "").casefold().strip()
        if not lowered:
            return "ambiguous"
        if any(term in lowered for term in ("cancela", "olvida eso", "otra consulta")):
            return "new_task"

        extracted = SearchPlanNormalizer.params_from_message(message)
        has_slot = bool(extracted) or bool(re.search(
            r"\b\d[\d.,]*\s*(?:alumnos?|estudiantes?|personas?|m2|m²|metros?)\b",
            lowered,
        ))
        explicit_new_property_query = (
            any(term in lowered for term in ("muéstrame", "muestrame", "busca", "quiero ver"))
            and any(term in lowered for term in (
                "departamento", "dúplex", "duplex", "casa", "oficina", "terreno"
            ))
            and not any(term in lowered for term in SCHOOL_TERMS)
        )
        if explicit_new_property_query:
            return "new_task"
        if has_slot:
            return "continuation"
        return "ambiguous"

    @classmethod
    def effective_message(cls, task: Dict[str, Any], latest_message: str) -> str:
        fields = task.get("collected_fields") or {}
        parts = ["Buscar terrenos candidatos para construir un colegio"]
        if fields.get("distrito"):
            parts.append(f"en {fields['distrito']}")
        if fields.get("area_min") is not None:
            parts.append(f"con área mínima de {fields['area_min']} m²")
        if fields.get("cantidad_alumnos") is not None:
            parts.append(f"para {fields['cantidad_alumnos']} alumnos")
        if fields.get("presupuesto_max") is not None:
            parts.append(f"con presupuesto máximo de {fields['presupuesto_max']}")
        return " ".join(parts) + f". Respuesta actual del usuario: {latest_message}"

    @staticmethod
    def clarification_question(task: Dict[str, Any]) -> str:
        labels = {
            "distrito": "el distrito o zona",
            "area_min": "el área mínima aproximada",
            "cantidad_alumnos": "la cantidad prevista de alumnos",
        }
        missing = task.get("missing_fields") or []
        if not missing:
            return ""
        requested = ", ".join(labels.get(field, field) for field in missing)
        return (
            f"Para continuar necesito {requested}. "
            "El presupuesto es opcional; si no lo indicas buscaré sin límite de precio. "
            "La zonificación educativa se validará por separado."
        )

    @staticmethod
    def _json_value(value: Any) -> Any:
        if hasattr(value, "as_integer_ratio"):
            try:
                return int(value) if value == int(value) else float(value)
            except (TypeError, ValueError):
                pass
        return value
