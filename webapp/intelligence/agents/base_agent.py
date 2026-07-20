"""
BaseAgent — Contrato abstracto para todos los agentes de la plataforma.

Define la interfaz que todo agente debe cumplir — es el equivalente de
BaseSkill pero para agentes. Incluye el ReActLoopMixin para el loop
de razonamiento iterativo.

SPEC: refactor_plataforma_agentes.md — Fase 1
SPEC: requisitos_completos_react_loop.md — Verificación de requisitos completos
"""

from __future__ import annotations

import logging
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Tipos compartidos
# ═══════════════════════════════════════════════════════════════════════════════


class AgentStatus(str, Enum):
    """Estados posibles de un paso del agente."""
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    DONE = "done"
    FAILED = "failed"
    MAX_ITERATIONS = "max_iterations"


@dataclass
class AgentStep:
    """Un paso individual dentro del loop ReAct de un agente."""
    iteration: int
    thought: str                      # razonamiento del LLM antes de actuar
    skill_used: Optional[str] = None  # None si decidió no usar ninguna skill
    skill_params: Optional[dict] = None
    skill_result: Optional[dict] = None
    status: AgentStatus = AgentStatus.THINKING
    error_message: Optional[str] = None  # SPEC precondiciones: mensaje de fallo explícito


@dataclass
class AgentResult:
    """Resultado final de la ejecución de un agente."""
    agent_name: str
    success: bool
    final_answer: Optional[dict] = None
    steps: List[AgentStep] = field(default_factory=list)
    iterations_used: int = 0
    error_message: Optional[str] = None
    confidence: float = 0.0           # autoevaluación del propio agente
    pending_requirements: List[str] = field(default_factory=list)

    def to_log(self) -> dict:
        """Convierte a dict para logging y persistencia (Fase 8)."""
        return {
            'agent_name': self.agent_name,
            'success': self.success,
            'iterations_used': self.iterations_used,
            'confidence': round(self.confidence, 4),
            'error_message': self.error_message,
            'pending_requirements': self.pending_requirements,
            'steps': [
                {
                    'iteration': s.iteration,
                    'thought': s.thought,
                    'skill_used': s.skill_used,
                    'skill_params': s.skill_params,
                    'status': s.status.value,
                }
                for s in self.steps
            ],
        }


@dataclass
class AgentDefinition:
    """Metadatos declarativos de un agente — análogo a los atributos de BaseSkill."""
    name: str                          # snake_case único, ej. "agente_propiedades"
    description: str                   # usado por el Supervisor para enrutar
    domain: str                        # publico, legal, marketing, gerencia, ti, general
    allowed_skills: List[str]          # nombres exactos registrados en SkillRegistry
    access_level: int = 1              # 1-5, igual que las skills
    max_iterations: int = 5
    system_prompt: str = ""            # rol y objetivo del agente
    is_active: bool = True
    budget_limit_usd: float = 0.05     # límite de costo por ejecución (default $0.05)


# ═══════════════════════════════════════════════════════════════════════════════
# Requirement — Requisito atómico de la consulta del usuario
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class Requirement:
    """Un requisito atómico extraído de la consulta del usuario.

    SPEC: requisitos_completos_react_loop.md — Sección 2.1
    Cada requisito es verificable de forma independiente.
    """
    id: str                           # ej. "req_0", "req_1"
    description: str                  # ej. "buscar terrenos en Cerro Colorado"
    kind: str                         # 'data' | 'format' | 'filter' | 'comparison' | 'other'
    satisfied: bool = False
    satisfied_by_skill: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Deterministic format detection (guardrail de piso, sin LLM)
# ═══════════════════════════════════════════════════════════════════════════════

FORMAT_KEYWORDS = {
    'carrusel': 'carrusel',
    'en lista': 'lista',
    'listado': 'lista',
    'en tabla': 'tabla',
    'matriz': 'matriz',
    'comparativa': 'comparativa',
    'en mapa': 'mapa',
}


def detect_format_requirement(original_message: str) -> Optional[str]:
    """Detección determinista de formato solicitado — sin llamada a LLM.

    SPEC: requisitos_completos_react_loop.md — Sección 2.2
    Guardrail de piso: si el usuario pidió un formato y extract_requirements()
    no lo detectó, se agrega automáticamente.
    """
    msg_lower = original_message.lower()
    for keyword, formato in FORMAT_KEYWORDS.items():
        if keyword in msg_lower:
            return formato
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# SKILL_SATISFIES_KIND — Mapeo skill → tipo de requisito que puede satisfacer
# ═══════════════════════════════════════════════════════════════════════════════
# SPEC: estado_monotonico_requisitos.md — Sección 2.1
# Cada skill solo puede satisfacer requisitos de su tipo correspondiente.
# Skills sin entrada en este dict no pueden satisfacer ningún requisito conocido.
# ═══════════════════════════════════════════════════════════════════════════════

SKILL_SATISFIES_KIND: dict[str, str] = {
    'busqueda_propiedades': 'data',
    'busqueda_exacta': 'data',
    'matching_hibrido': 'data',
    'acm_analisis': 'data',
    'reporte_precios_zona': 'data',
    'mis_requerimientos': 'data',
    'matching_OD': 'data',
    'formatear_propiedades': 'format',
    'metricas_marketing': 'data',
    'campanas_activas': 'data',
    'mis_matches': 'data',
    'mis_propiedades': 'data',
}


# ═══════════════════════════════════════════════════════════════════════════════
# Field name mapping for busqueda_exacta filters
# ═══════════════════════════════════════════════════════════════════════════════

FIELD_NAME_MAP = {
    'tipo': 'property_type_name',
    'tipo_propiedad': 'property_type_name',
    'distrito': 'district_name',
    'precio_min': 'price',
    'precio_max': 'price',
    'precio': 'price',
    'habitaciones': 'bedrooms',
    'dormitorios': 'bedrooms',
    'banos': 'bathrooms',
    'area_min': 'built_area',
    'area_max': 'built_area',
    'operacion': 'operation_type_name',
    'condicion': 'property_status_name',
}


# ═══════════════════════════════════════════════════════════════════════════════
# _result_item_count — Extrae cantidad real de items de un resultado de skill
# ═══════════════════════════════════════════════════════════════════════════════
# ADDENDUM: formatear_propiedades_real — Sección 3
# Todas las skills devuelven 'total' de forma consistente.
# Un dict con total=0 sigue siendo truthy en Python, pero NO debe satisfacer
# un requisito. Esta función reemplaza checks de bool(skill_result).
# ═══════════════════════════════════════════════════════════════════════════════


def _result_item_count(skill_result: Any) -> int:
    """Extrae la cantidad real de items de un resultado de skill,
    tolerando las 3 formas distintas que existen hoy en el catálogo:
      - lista plana (busqueda_propiedades)
      - dict con clave 'total' + 'resultados' (busqueda_exacta)
      - dict con clave 'total' + 'html' (formatear_propiedades)

    ADDENDUM 2: Sección 3
    """
    if skill_result is None:
        return 0

    # Caso 1: el propio data es una lista (busqueda_propiedades)
    if isinstance(skill_result, list):
        return len(skill_result)

    if isinstance(skill_result, dict):
        # Caso 2: dict con 'total' directo (busqueda_exacta, formatear_propiedades)
        if 'total' in skill_result:
            return skill_result.get('total') or 0
        # Caso 3: dict con 'total_encontrados' (variante de metadata)
        if 'total_encontrados' in skill_result:
            return skill_result.get('total_encontrados') or 0
        # Fallback: primera lista que aparezca dentro del dict
        for value in skill_result.values():
            if isinstance(value, list):
                return len(value)

    return 0


DATA_SKILLS = {'busqueda_propiedades', 'busqueda_exacta', 'matching_hibrido', 'acm_analisis'}


# ═══════════════════════════════════════════════════════════════════════════════
# BaseAgent — Contrato abstracto
# ═══════════════════════════════════════════════════════════════════════════════


class BaseAgent(ABC):
    """
    Clase base abstracta para todos los agentes de la plataforma.

    Cada agente concreto debe:
    - Definir `definition: AgentDefinition`
    - Implementar `run(message, context) -> AgentResult`
    """

    definition: AgentDefinition

    @abstractmethod
    def run(self, message: str, context: Optional[dict] = None) -> AgentResult:
        """
        Ejecuta el loop ReAct completo.

        Args:
            message: Mensaje del usuario en lenguaje natural
            context: Contexto del usuario (nivel, perfil, sesión, etc.)

        Returns:
            AgentResult con el resultado estructurado
        """
        ...

    def _validate_skill_access(self, skill_name: str) -> bool:
        """
        Guardrail obligatorio: nunca ejecutar una skill fuera de allowed_skills.
        """
        return skill_name in self.definition.allowed_skills

    def _check_budget(self, accumulated_cost_usd: float) -> bool:
        """Verifica si el agente aún tiene presupuesto."""
        return accumulated_cost_usd < self.definition.budget_limit_usd

    def get_schema(self) -> dict:
        """Retorna schema del agente para el Supervisor y diagnóstico."""
        return {
            'name': self.definition.name,
            'description': self.definition.description,
            'domain': self.definition.domain,
            'allowed_skills': self.definition.allowed_skills,
            'access_level': self.definition.access_level,
            'max_iterations': self.definition.max_iterations,
            'is_active': self.definition.is_active,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ReActLoopMixin — Loop de razonamiento iterativo con checklist de requisitos
# ═══════════════════════════════════════════════════════════════════════════════


class ReActLoopMixin:
    """
    Mixin que implementa el loop ReAct (Think → Act → Observe)
    con verificación de requisitos completos.

    SPEC: requisitos_completos_react_loop.md

    A diferencia del código anterior, este mixin:
    1. Extrae requisitos atómicos de la consulta al inicio (extract_requirements)
    2. Mantiene original_message fijo en todo el loop (nunca se reescribe)
    3. _observe() verifica contra el checklist completo, no contra el último paso
    4. _think() siempre ve la consulta original + qué requisitos faltan
    5. Si se pide formato (carrusel/lista) y no se aplicó, el loop continúa
    """

    definition: AgentDefinition  # provisto por la clase concreta

    # ── Extracción de requisitos ──────────────────────────────────────────

    def extract_requirements(self, original_message: str) -> List[Requirement]:
        """
        Descompone la consulta en requisitos atómicos verificables.

        SPEC: requisitos_completos_react_loop.md — Sección 2.1
        SPEC: requisito_formato_fantasma.md — Sección 2.1 y 2.2

        REGLA ESTRICTA: NO genera requisitos de tipo 'format'.
        El formato se detecta por separado en detect_format_requirement()
        usando keywords deterministas, NO por LLM.

        Se llama UNA VEZ al inicio del loop, nunca se reescribe después.
        """
        from ..services.llm import LLMService

        prompt = f"""Descompón esta consulta del usuario en requisitos atómicos que la respuesta final debe cumplir.

IMPORTANTE — REGLA ESTRICTA SOBRE FORMATO:
NO generes ningún requisito relacionado con CÓMO se presenta la información
(formato visual, presentación, claridad, estructura de la respuesta).
Eso se detecta por otro sistema, de forma automática, y NO es tu responsabilidad.
Solo genera requisitos sobre QUÉ información se necesita, QUÉ filtros aplicar,
o QUÉ comparación/análisis se pide — nunca sobre cómo debe verse la respuesta.

Presta especial atención a: filtros específicos, comparaciones,
y cualquier "y además" / "y también" en la consulta.

Consulta: "{original_message}"

Responde SOLO con JSON:
{{"requirements": [
    {{"description": "...", "kind": "data|filter|comparison|other"}}
]}}"""

        try:
            success, msg, response = LLMService._call_deepseek_api(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="Eres un extractor de requisitos. Devuelve SOLO JSON.",
            )
            if success and response:
                content = response.get('content', '')
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    data = json.loads(json_match.group())
                    reqs = data.get('requirements', [])

                    # Guardrail defensivo (SPEC requisito_formato_fantasma — Sección 2.2):
                    # Si el LLM generó 'format' pese a la instrucción, se descarta aquí.
                    # El único lugar autorizado para crear requisitos de formato
                    # es detect_format_requirement().
                    reqs = [r for r in reqs if r.get('kind') != 'format']

                    return [
                        Requirement(id=f"req_{i}", description=r.get('description', ''),
                                    kind=r.get('kind', 'other'))
                        for i, r in enumerate(reqs)
                    ]
        except Exception as e:
            logger.warning(f"[Requirements] Error extrayendo requisitos: {e}")

        # Fallback: requisito genérico
        return [Requirement(id="req_0", description=original_message, kind="data")]

    # ── Helpers de requisitos ────────────────────────────────────────────

    @staticmethod
    def _summarize_steps(steps: List[AgentStep]) -> str:
        """Crea resumen de pasos ejecutados para el prompt.
        
        SPEC: precondiciones_skills.md — Sección 2.1
        Muestra explícitamente qué skills fallaron y por qué,
        para que el LLM no las repita.
        """
        if not steps:
            return "(ninguno todavía)"
        lines = []
        for s in steps[-5:]:  # últimos 5 pasos
            if s.status == AgentStatus.FAILED:
                error = s.error_message or "sin detalle"
                lines.append(
                    f"  - Intentaste '{s.skill_used}' y FALLÓ: {error}. "
                    f"No la repitas."
                )
            elif s.skill_used:
                lines.append(
                    f"  - Ejecutaste '{s.skill_used}' con éxito."
                )
            else:
                lines.append(f"  - Paso {s.iteration}: {s.thought[:80]}")
        return "\n".join(lines)

    @staticmethod
    def _update_requirements_status(requirements: List[Requirement], step: AgentStep):
        """Actualiza estado de requisitos según resultado de UN step.

        SPEC: estado_monotonico_requisitos.md — Sección 2.2

        Reglas invariantes:
        1. MONOTÓNICO: un requisito satisfied=True nunca vuelve a False.
        2. FILTRADO POR TIPO: un step solo afecta requisitos cuyo 'kind'
           coincide con lo que esa skill puede satisfacer (SKILL_SATISFIES_KIND).
        3. Un step fallido (AgentStatus.FAILED) nunca satisface nada.
        """
        if step.status == AgentStatus.FAILED or not step.skill_used:
            return  # nada que actualizar; NO se toca ningún requisito

        skill_kind = SKILL_SATISFIES_KIND.get(step.skill_used)
        if skill_kind is None:
            return  # skill sin mapeo conocido: no se asume nada

        # ADDENDUM: usar _result_item_count en vez de bool(skill_result)
        # Un dict con total=0 sigue siendo truthy pero no debe satisfacer requisitos
        item_count = _result_item_count(step.skill_result)
        if item_count == 0:
            return  # ADDENDUM: total=0 no satisface nada, aunque SkillResult.success=True

        for requirement in requirements:
            was_satisfied = requirement.satisfied

            if requirement.satisfied:
                continue  # regla 1: ya estaba cumplido, no se re-evalúa

            if requirement.kind == skill_kind:
                requirement.satisfied = True
                requirement.satisfied_by_skill = step.skill_used
                logger.info(
                    f"[ReAct] Requisito '{requirement.description}' "
                    f"recién cumplido por '{step.skill_used}'"
                )

            # Alerta si algún requisito se revierte (viola invariante monotónica)
            if was_satisfied and not requirement.satisfied:
                logger.error(
                    f"[ReAct] ALERTA: requisito '{requirement.description}' "
                    f"se revirtió de cumplido a pendiente. "
                    f"Esto viola la invariante monotónica."
                )

    # ── THINK ────────────────────────────────────────────────────────────

    def _think(self, original_message: str, requirements: List[Requirement],
               steps: List[AgentStep], context: dict) -> dict:
        """
        El LLM decide la próxima acción.

        SPEC: requisitos_completos_react_loop.md — Sección 2.4
        SPEC: precondiciones_skills.md — Sección 2 (filtro de skills disponibles)

        original_message SIEMPRE es el mismo en todas las iteraciones.
        Solo se muestran las skills que son EJECUTABLES en este momento.
        """
        from ..services.llm import LLMService
        from .skill_preconditions import get_available_skills

        pending = [r.description for r in requirements if not r.satisfied]
        completed = [r.description for r in requirements if r.satisfied]

        steps_context = self._summarize_steps(steps)

        # Filtrar skills disponibles según precondiciones y fallos
        available_now = get_available_skills(self.definition.allowed_skills, steps, context)
        excluded = set(self.definition.allowed_skills) - set(available_now)

        prompt = self.definition.system_prompt + f"""

CONSULTA ORIGINAL DEL USUARIO (nunca cambia durante esta tarea):
"{original_message}"

REQUISITOS YA CUMPLIDOS:
{chr(10).join(f'  ✅ {c}' for c in completed) if completed else '  (ninguno todavía)'}

REQUISITOS PENDIENTES (debes seguir trabajando hasta cubrir todos):
{chr(10).join(f'  ⏳ {p}' for p in pending) if pending else '  ✅ Todos los requisitos están cubiertos.'}

PASOS EJECUTADOS HASTA AHORA:
{steps_context}

SKILLS DISPONIBLES AHORA (solo estas son válidas en este momento):
{', '.join(available_now) if available_now else 'NINGUNA — responde con is_final=true'}

{chr(10).join(f'🚫 SKILLS NO DISPONIBLES: {e} (requieren paso previo o fallaron repetidamente)' for e in excluded) if excluded else ''}

Si quedan requisitos PENDIENTES, NO marques is_final=true todavía.
Debes elegir UNA de las SKILLS DISPONIBLES AHORA que ayude a cumplir ALGUNO de los requisitos pendientes.
Si el requisito pendiente es de formato (carrusel, lista, tabla), usa la skill 'formatear_propiedades'.
NO elijas skills de la lista NO DISPONIBLES.

Responde SOLO con JSON en este formato:
{{
  "reasoning": "explica brevemente tu razonamiento",
  "is_final": true|false,
  "skill_name": "nombre_de_skill_o_null_si_es_final",
  "params": {{ "param1": "valor1" }} si aplica,
  "final_answer": {{ "respuesta": "..." }} si is_final=true,
  "confidence": 0.0 a 1.0
}}"""

        try:
            success, msg, response = LLMService._call_deepseek_api(
                messages=[{"role": "user", "content": original_message}],
                system_prompt=prompt,
            )
            if success and response:
                content = response.get('content', '')
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"[ReAct] Error en _think: {e}")

        # Fallback seguro
        return {
            'reasoning': 'error en razonamiento, usando fallback',
            'is_final': True,
            'final_answer': {'error': 'No se pudo procesar la consulta'},
            'confidence': 0.0,
        }

    # ── OBSERVE ──────────────────────────────────────────────────────────

    def _observe(self, original_message: str, step: AgentStep,
                 requirements: List[Requirement], steps: List[AgentStep],
                 context: dict) -> dict:
        """
        Evalúa si TODOS los requisitos están cumplidos.

        SPEC: requisitos_completos_react_loop.md — Sección 2.3
        NO solo verifica si hay datos — verifica contra el checklist completo.

        1. Marca requisitos que esta skill pudo haber cumplido
        2. Verificación determinista de formato (guardrail de piso, sin LLM)
        3. Si todo cumplido → is_sufficient=True
        4. Si falta algo → is_sufficient=False con detalle
        """
        # 1. Actualizar estado de requisitos según la skill ejecutada
        self._update_requirements_status(requirements, step)

        # 2. Guardrail determinista: verificar formato pendiente
        # SPEC: requisito_formato_fantasma.md — Sección 2.4
        FORMATOS_REALES = {'carrusel', 'matriz', 'lista'}
        format_req = next((r for r in requirements if r.kind == 'format' and not r.satisfied), None)
        if format_req:
            # Verificar si la descripción menciona un formato real
            desc_lower = format_req.description.lower()
            es_formato_valido = any(f in desc_lower for f in FORMATOS_REALES)

            if not es_formato_valido:
                # Requisito de formato no ejecutable — auto-satisfacer
                # para no bloquear el loop con algo que ninguna skill real puede cumplir
                logger.warning(
                    f"[ReAct] Requisito de formato no reconocido, "
                    f"auto-satisfecho: {format_req.description}"
                )
                format_req.satisfied = True
            else:
                # Formato válido: verificar si ya se llamó a formatear_propiedades
                formatting_called = any(
                    s.skill_used == 'formatear_propiedades' for s in steps
                )
                if not formatting_called:
                    return {
                        'is_sufficient': False,
                        'reason': f"Falta cumplir requisito de formato: {format_req.description}",
                        'pending_requirements': [r.description for r in requirements if not r.satisfied],
                        'confidence': 0.5,
                    }

        # 3. Detectar "cero resultados genuino" (ADDENDUM: Sección 4)
        # Si una data skill devolvió total=0 y ya intentamos 2 veces,
        # es momento de responder "no hay resultados" en vez de seguir intentando.
        if step.skill_used in DATA_SKILLS and _result_item_count(step.skill_result) == 0:
            data_attempts = sum(1 for s in steps if s.skill_used in DATA_SKILLS)
            if data_attempts >= 2:
                logger.info(
                    f"[ReAct] Cero resultados tras {data_attempts} intentos "
                    f"de búsqueda. Concluyendo con respuesta honesta."
                )
                return {
                    'is_sufficient': True,
                    'reason': 'búsqueda sin resultados confirmada tras reintento',
                    'confidence': 0.9,
                    'final_answer_override': {
                        'total': 0,
                        'mensaje': 'No se encontraron propiedades que coincidan con tu búsqueda.',
                    },
                }

        # 4. Verificar si todos los requisitos están cumplidos
        pending = [r for r in requirements if not r.satisfied]
        if not pending:
            return {
                'is_sufficient': True,
                'reason': 'Todos los requisitos cumplidos',
                'confidence': 1.0,
            }

        # 5. Aún hay requisitos pendientes
        return {
            'is_sufficient': False,
            'reason': f"{len(pending)} requisito(s) pendiente(s): {', '.join(r.description for r in pending)}",
            'pending_requirements': [r.description for r in pending],
            'confidence': 0.3,
        }

    # ── RUN (reescrito) ──────────────────────────────────────────────────

    def run(self, message: str, context: Optional[dict] = None) -> AgentResult:
        """
        ReAct loop con verificación de requisitos completos.

        SPEC: requisitos_completos_react_loop.md — Sección 2.5

        Args:
            message: Mensaje original del usuario (se mantiene fijo todo el loop)
            context: Contexto de ejecución

        Returns:
            AgentResult con resultado estructurado y requisitos pendientes
        """
        from ..services.llm import LLMService
        from ..skills.orchestrator import ExecutionContext, SkillOrchestrator

        context = context or {}
        original_message = message  # NUNCA se reescribe
        agent_name = self.definition.name
        steps: List[AgentStep] = []
        accumulated_cost = 0.0

        # ── 1. Extraer requisitos (una sola vez al inicio) ──
        requirements = self.extract_requirements(original_message)
        logger.info(
            f"[ReAct] {agent_name}: {len(requirements)} requisito(s) extraídos: "
            f"{[r.description for r in requirements]}"
        )

        # ── 2. Guardrail determinista: detectar formato por keywords ──
        format_needed = detect_format_requirement(original_message)
        if format_needed and not any(r.kind == 'format' for r in requirements):
            requirements.append(Requirement(
                id=f"req_{len(requirements)}",
                description=f"presentar en formato {format_needed}",
                kind='format',
            ))
            logger.info(
                f"[ReAct] Guardrail: agregado requisito de formato "
                f"'{format_needed}' por detección determinista"
            )

        # ── 3. Loop ReAct ──
        for iteration in range(self.definition.max_iterations):
            # THINK
            thought_result = self._think(original_message, requirements, steps, context)
            step = AgentStep(
                iteration=iteration,
                thought=thought_result.get('reasoning', ''),
                skill_used=thought_result.get('skill_name'),
                skill_params=thought_result.get('params'),
                status=AgentStatus.THINKING,
            )

            # Si el LLM decide que ya terminó
            if thought_result.get('is_final', False):
                # Verificar que realmente todos los requisitos están cumplidos
                pending = [r for r in requirements if not r.satisfied]
                if not pending:
                    step.status = AgentStatus.DONE
                    steps.append(step)
                    logger.info(
                        f"[ReAct] {agent_name} decisión final "
                        f"en iteración {iteration} — todos los requisitos cumplidos"
                    )
                    return AgentResult(
                        agent_name=agent_name,
                        success=True,
                        final_answer=thought_result.get('final_answer'),
                        steps=steps,
                        iterations_used=iteration + 1,
                        confidence=thought_result.get('confidence', 0.8),
                        pending_requirements=[],
                    )
                else:
                    # El LLM quiere terminar pero hay requisitos pendientes
                    # Forzar el loop a continuar
                    logger.info(
                        f"[ReAct] {agent_name} intentó finalizar pero faltan "
                        f"{len(pending)} requisito(s). Continuando loop."
                    )
                    # Asegurar que el LLM intente con una skill
                    thought_result['is_final'] = False

            skill_name = step.skill_used

            # Guardrail: validar skill permitida
            if skill_name and not self._validate_skill_access(skill_name):
                logger.warning(
                    f"[ReAct] {agent_name} intentó usar skill "
                    f"'{skill_name}' no autorizada. Omitiendo."
                )
                step.status = AgentStatus.FAILED
                steps.append(step)
                continue

            # Guardrail: verificar presupuesto
            if not self._check_budget(accumulated_cost):
                logger.warning(
                    f"[ReAct] {agent_name} excedió presupuesto "
                    f"(${accumulated_cost:.6f} > ${self.definition.budget_limit_usd})."
                )
                pending_descriptions = [r.description for r in requirements if not r.satisfied]
                steps.append(step)
                return AgentResult(
                    agent_name=agent_name,
                    success=False,
                    final_answer=None,
                    steps=steps,
                    iterations_used=iteration + 1,
                    error_message=f"Presupuesto excedido (${accumulated_cost:.6f})",
                    confidence=0.0,
                    pending_requirements=pending_descriptions,
                )

            # ACT: ejecutar la skill
            if skill_name:
                # SPEC precondiciones: sustitución determinista si la skill no puede ejecutarse
                from .skill_preconditions import resolve_skill_substitution
                resolved_skill = resolve_skill_substitution(skill_name, steps)
                if resolved_skill != skill_name:
                    logger.info(
                        f"[ReAct] {agent_name} sustitución determinista: "
                        f"'{skill_name}' → '{resolved_skill}' (sin datos previos)"
                    )
                    skill_name = resolved_skill
                    step.skill_used = resolved_skill

                step.status = AgentStatus.ACTING
                try:
                    from ..skills.registry import SkillRegistry
                    from ..skills.cache import SkillCache
                    _orch = SkillOrchestrator(SkillRegistry(), SkillCache())
                    exec_ctx = ExecutionContext(
                        user_id=context.get('user_id'),
                        conversation_id=context.get('conversation_id'),
                        session_id=context.get('session_id', context.get('conversation_id', '')),
                        metadata={'agent_context': context},
                    )

                    # Pipeline automático: inyectar resultados y filtrar
                    params = dict(step.skill_params or {})
                    if skill_name == 'busqueda_exacta':
                        # Inyectar 'propiedades' desde skill anterior
                        if 'propiedades' not in params:
                            for prev_step in reversed(steps):
                                prev_data = prev_step.skill_result
                                if isinstance(prev_data, dict):
                                    prop_list = (
                                        prev_data.get('resultados')
                                        or prev_data.get('properties')
                                        or prev_data.get('data', [])
                                    )
                                    if isinstance(prop_list, list) and prop_list:
                                        params['propiedades'] = prop_list
                                        break
                                elif isinstance(prev_data, list) and prev_data:
                                    params['propiedades'] = prev_data
                                    break

                        # Generar 'filtros' desde parámetros del LLM
                        # con mapeo correcto de nombres de campo
                        if 'filtros' not in params:
                            reserved_keys = {'propiedades', 'ordenar_por', 'direccion'}
                            raw_filters = {}
                            for k, v in params.items():
                                if k not in reserved_keys:
                                    raw_filters[k] = v
                            if not raw_filters:
                                # Detectar desde la consulta original
                                # ADDENDUM 2: reutilizar mapeos de busqueda_propiedades
                                msg_lower = original_message.lower()
                                try:
                                    from ..skills.propiedades.skill import TIPO_PROPIEDAD_MAP
                                    for keyword, tipo in TIPO_PROPIEDAD_MAP.items():
                                        if keyword in msg_lower:
                                            raw_filters['tipo'] = tipo
                                            break
                                except ImportError:
                                    # Fallback si no se puede importar
                                    tipo_fallback = {'terreno': 'Terreno', 'casa': 'Casa',
                                                     'departamento': 'Departamento', 'local': 'Local Comercial',
                                                     'oficina': 'Oficina'}
                                    for keyword, tipo in tipo_fallback.items():
                                        if keyword in msg_lower:
                                            raw_filters['tipo'] = tipo
                                            break
                                distritos = ['Cayma', 'Yanahuara', 'Cercado', 'Sachaca',
                                            'Miraflores', 'Cerro Colorado', 'Bustamante',
                                            'Paucarpata', 'Mariano Melgar']
                                for d in distritos:
                                    if d.lower() in msg_lower:
                                        raw_filters['distrito'] = d
                                        break
                            # Mapear nombres de campo al formato correcto
                            if raw_filters:
                                params['filtros'] = {
                                    FIELD_NAME_MAP.get(k, k): v
                                    for k, v in raw_filters.items()
                                }

                    skill_result = _orch.execute_skill(
                        skill_name=skill_name,
                        parameters=params,
                        context=exec_ctx,
                    )
                    step.skill_result = skill_result.data if hasattr(skill_result, 'data') else {}
                    accumulated_cost += 0.0001
                except Exception as e:
                    logger.error(
                        f"[ReAct] {agent_name} error ejecutando "
                        f"skill '{skill_name}': {e}"
                    )
                    step.status = AgentStatus.FAILED
                    step.skill_result = {'error': str(e)}
                    step.error_message = str(e)[:200]

            # OBSERVE: verificar contra el checklist completo
            steps.append(step)
            observation = self._observe(original_message, step, requirements, steps, context)
            step.status = AgentStatus.OBSERVING

            if observation.get('is_sufficient', False):
                logger.info(
                    f"[ReAct] {agent_name} resultado suficiente "
                    f"en iteración {iteration}: {observation.get('reason', 'todos cumplidos')}"
                )
                return AgentResult(
                    agent_name=agent_name,
                    success=True,
                    final_answer=thought_result.get('final_answer', step.skill_result),
                    steps=steps,
                    iterations_used=iteration + 1,
                    confidence=observation.get('confidence', 0.7),
                    pending_requirements=[],
                )

            # Si no es suficiente, el loop continúa
            # _think() en la próxima vuelta ve exactamente qué requisitos faltan
            logger.info(
                f"[ReAct] {agent_name} iteración {iteration}: "
                f"{observation.get('reason', 'requisitos pendientes')}"
            )

        # ── Max iterations sin completar todos los requisitos ──
        pending_descriptions = [r.description for r in requirements if not r.satisfied]
        logger.warning(
            f"[ReAct] {agent_name} alcanzó máximo de "
            f"{self.definition.max_iterations} iteraciones. "
            f"Requisitos pendientes: {pending_descriptions}"
        )
        return AgentResult(
            agent_name=agent_name,
            success=False,
            final_answer=None,
            steps=steps,
            iterations_used=self.definition.max_iterations,
            error_message=f"max_iterations con requisitos pendientes: {pending_descriptions}",
            confidence=0.0,
            pending_requirements=pending_descriptions,
        )
