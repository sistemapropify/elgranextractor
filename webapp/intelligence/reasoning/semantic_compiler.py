"""Compilador LLM: lenguaje natural y contexto activo -> contrato semántico."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import json
import re
from typing import Any

from .contracts import SemanticTaskState
from .validators import PROPERTY_FIELDS, SemanticTaskValidator, ValidationResult


@dataclass
class SemanticCompilationResult:
    status: str
    task: SemanticTaskState | None
    validation: ValidationResult
    error: str = ""
    raw_preview: str = ""

    @property
    def success(self) -> bool:
        return self.status == "completed" and self.task is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "success": self.success,
            "task": self.task.to_dict() if self.task else None,
            "validation": self.validation.to_dict(),
            "error": self.error,
            "raw_preview": self.raw_preview,
        }


class SemanticIntentCompiler:
    """Interpreta toda la consulta sin acoplarla a una skill específica."""

    MAX_RAW_PREVIEW = 400
    MAX_CONTEXT_CHARS = 6000

    @classmethod
    def compile(
        cls,
        *,
        query: str,
        active_task: dict[str, Any] | None = None,
        conversation_excerpt: list[dict[str, Any]] | None = None,
    ) -> SemanticCompilationResult:
        prompt = cls._build_prompt(
            query=query,
            active_task=active_task,
            conversation_excerpt=conversation_excerpt,
        )
        success, api_message, response = cls._call_llm(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=(
                "Eres un compilador semántico. No respondas al usuario y no "
                "expliques tu razonamiento. Devuelve únicamente el JSON solicitado."
            ),
            caller_app="semantic_intent_compiler",
            endpoint="compile",
        )
        if not success or not isinstance(response, dict):
            return SemanticCompilationResult(
                status="failed",
                task=None,
                validation=ValidationResult(),
                error=str(api_message or "Semantic compiler unavailable")[:300],
            )
        raw = response.get("content", "")
        payload = cls._parse_json(raw)
        if not payload:
            return SemanticCompilationResult(
                status="failed",
                task=None,
                validation=ValidationResult(),
                error="El compilador no devolvió JSON válido.",
                raw_preview=str(raw or "")[:cls.MAX_RAW_PREVIEW],
            )
        return cls.compile_payload(payload, raw_preview=str(raw or ""))

    @classmethod
    def compile_payload(
        cls,
        payload: dict[str, Any],
        *,
        raw_preview: str = "",
    ) -> SemanticCompilationResult:
        try:
            task = SemanticTaskState.from_dict(payload)
        except (KeyError, TypeError, ValueError) as exc:
            return SemanticCompilationResult(
                status="invalid",
                task=None,
                validation=ValidationResult(),
                error=f"Contrato semántico inválido: {exc}"[:300],
                raw_preview=raw_preview[:cls.MAX_RAW_PREVIEW],
            )

        task.refresh_status()
        validation = SemanticTaskValidator.validate(task)
        return SemanticCompilationResult(
            status="completed" if validation.valid else "invalid",
            task=task,
            validation=validation,
            error="" if validation.valid else "El contrato no superó la validación.",
            raw_preview=raw_preview[:cls.MAX_RAW_PREVIEW],
        )

    @classmethod
    def _build_prompt(
        cls,
        *,
        query: str,
        active_task: dict[str, Any] | None,
        conversation_excerpt: list[dict[str, Any]] | None,
    ) -> str:
        allowed_fields = {
            name: value_type for name, value_type in PROPERTY_FIELDS.items()
        }
        context = {
            "active_task": active_task or {},
            "recent_messages": (conversation_excerpt or [])[-12:],
        }
        encoded_context = json.dumps(
            context, ensure_ascii=False, default=str
        )[:cls.MAX_CONTEXT_CHARS]
        return f"""Compila la consulta completa a un contrato semántico ejecutable.

CONSULTA ACTUAL:
{query[:2000]}

CONTEXTO:
{encoded_context}

CAMPOS AUTORIZADOS:
{json.dumps(allowed_fields, ensure_ascii=False)}

OPERADORES:
eq, neq, gt, gte, lt, lte, in, not_in, contains, between.

REGLAS OBLIGATORIAS:
- Conserva todas las restricciones, negaciones, alternativas y correcciones.
- Para comparar dos atributos usa operandos kind="field" a ambos lados.
- Para listas usa right.kind="set" y operator="in" o "not_in".
- "Cualquier distrito", "sin importar el distrito" o equivalentes significa
  que NO debe existir una restricción district.
- No conviertas palabras vagas como pocos, barato, grande o cerca en números.
  Regístralas en ambiguities con una pregunta concreta.
- Clasifica la relación del turno:
  new_task = petición independiente; continuation = agrega criterios;
  correction = sustituye o elimina criterios; cancelled = cancela la tarea;
  ambiguous = no hay evidencia suficiente para decidir.
- Si existe active_task y la relación es continuation o correction, devuelve
  el estado COMPLETO resultante, no solamente lo expresado en el último turno.
- Conserva el mismo ID para toda restricción que sobreviva del active_task.
- transition.carried_constraint_ids debe enumerar cada ID anterior que continúa.
- transition.added_constraint_ids debe enumerar cada ID nuevo.
- transition.removed_constraint_ids debe enumerar cada ID anterior eliminado y
  esos IDs no pueden aparecer en constraints.
- Nunca pierdas una restricción anterior sin declararla como eliminada.
- Para new_task no conserves ni elimines IDs de la tarea anterior.
- No inventes campos, valores, presupuesto, ubicación ni características.
- Cada constraint y ambiguity requiere un id único.
- confidence debe estar entre 0 y 1.
- objective debe ser search_properties, property_detail,
  compare_properties, analyze_market u other.
- status inicial debe ser planning.

FORMATO:
{{
  "objective": "search_properties",
  "entity": "property",
  "original_query": "texto del usuario",
  "effective_query": "consulta completa con contexto resuelto",
  "transition": {{
    "relationship": "new_task",
    "carried_constraint_ids": [],
    "added_constraint_ids": ["c1"],
    "removed_constraint_ids": [],
    "reason": "petición independiente"
  }},
  "constraints": [
    {{
      "id": "c1",
      "left": {{"kind": "field", "value": "property_type", "unit": null}},
      "operator": "eq",
      "right": {{"kind": "literal", "value": "Casa", "unit": null}},
      "required": true,
      "confidence": 0.99,
      "source_text": "fragmento de la consulta",
      "source_turn": 0,
      "metadata": {{}}
    }}
  ],
  "preferences": [],
  "ambiguities": [],
  "assumptions": [],
  "evidence": [],
  "attempts": [],
  "status": "planning",
  "confidence": 0.95,
  "schema_version": "2"
}}

Devuelve solamente un objeto JSON."""

    @staticmethod
    def _call_llm(**kwargs):
        """Carga el servicio LLM solo al ejecutar una compilación real."""
        from ..services.llm import LLMService

        return LLMService._call_deepseek_api(**kwargs)

    @staticmethod
    def _parse_json(content: Any) -> dict[str, Any] | None:
        if isinstance(content, dict):
            return content
        normalized = str(content or "").strip()
        normalized = re.sub(
            r"^\x60\x60\x60(?:json)?\s*|\s*\x60\x60\x60$",
            "",
            normalized,
            flags=re.IGNORECASE,
        ).strip()
        match = re.search(r"\{[\s\S]*\}", normalized)
        if not match:
            return None
        candidate = match.group()
        try:
            value = json.loads(candidate)
        except (TypeError, ValueError):
            try:
                value = ast.literal_eval(candidate)
            except (SyntaxError, ValueError):
                return None
        return value if isinstance(value, dict) else None
