"""
BaseAgent — Contrato abstracto para todos los agentes de la plataforma.

Define la interfaz que todo agente debe cumplir — es el equivalente de
BaseSkill pero para agentes. Incluye el ReActLoopMixin para el loop
de razonamiento iterativo.

SPEC: refactor_plataforma_agentes.md — Fase 1
"""

from __future__ import annotations

import logging
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

    def to_log(self) -> dict:
        """Convierte a dict para logging y persistencia (Fase 8)."""
        return {
            'agent_name': self.agent_name,
            'success': self.success,
            'iterations_used': self.iterations_used,
            'confidence': round(self.confidence, 4),
            'error_message': self.error_message,
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

        Esta validación vive en código, no depende de que el LLM 'se porte bien'.
        """
        return skill_name in self.definition.allowed_skills

    def _check_budget(self, accumulated_cost_usd: float) -> bool:
        """
        Verifica si el agente aún tiene presupuesto para seguir iterando.

        Args:
            accumulated_cost_usd: Costo acumulado de esta ejecución

        Returns:
            True si está dentro del presupuesto, False si debe cortar
        """
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
# ReActLoopMixin — Loop de razonamiento iterativo
# ═══════════════════════════════════════════════════════════════════════════════


class ReActLoopMixin:
    """
    Mixin que implementa el loop ReAct (Think → Act → Observe).

    Los agentes concretos pueden heredar este mixin para obtener el loop
    estándar, o implementar su propio run() si necesitan comportamiento específico.

    Dependencias externas (inyectadas via context):
    - LLMService._call_deepseek_api() para _think() y _observe()
    - SkillOrchestrator.execute() para ejecutar skills
    - AIConsumptionLog para tracking de costos
    """

    definition: AgentDefinition  # provisto por la clase concreta

    def run(self, message: str, context: Optional[dict] = None) -> AgentResult:
        """
        ReAct loop estándar: pensar → actuar → observar → repetir o finalizar.

        Args:
            message: Mensaje del usuario
            context: Contexto de ejecución

        Returns:
            AgentResult con el resultado final
        """
        from ..services.llm import LLMService
        from ..skills.orchestrator import SkillOrchestrator

        context = context or {}
        steps: List[AgentStep] = []
        agent_name = self.definition.name
        accumulated_cost = 0.0

        for iteration in range(self.definition.max_iterations):
            # ── THINK: el LLM decide qué hacer ──
            thought_result = self._think(message, context, steps)
            step = AgentStep(
                iteration=iteration,
                thought=thought_result.get('reasoning', ''),
                skill_used=thought_result.get('skill_name'),
                skill_params=thought_result.get('params'),
                status=AgentStatus.THINKING,
            )

            # Si el LLM decide que ya tiene suficiente para responder
            if thought_result.get('is_final', False):
                step.status = AgentStatus.DONE
                steps.append(step)
                logger.info(
                    f"[ReAct] {agent_name} decisi\u00f3n final "
                    f"en iteraci\u00f3n {iteration}: {thought_result.get('reasoning', '')[:100]}"
                )
                return AgentResult(
                    agent_name=agent_name,
                    success=True,
                    final_answer=thought_result.get('final_answer'),
                    steps=steps,
                    iterations_used=iteration + 1,
                    confidence=thought_result.get('confidence', 0.8),
                )

            skill_name = step.skill_used
            # ── Guardrail: validar que la skill está permitida ──
            if skill_name and not self._validate_skill_access(skill_name):
                logger.warning(
                    f"[ReAct] {agent_name} intent\u00f3 usar skill "
                    f"'{skill_name}' no autorizada. Omitiendo."
                )
                step.status = AgentStatus.FAILED
                steps.append(step)
                continue

            # ── Guardrail: verificar presupuesto ──
            if not self._check_budget(accumulated_cost):
                logger.warning(
                    f"[ReAct] {agent_name} excedi\u00f3 presupuesto "
                    f"(${accumulated_cost:.6f} > ${self.definition.budget_limit_usd}). "
                    f"Cortando loop."
                )
                step.status = AgentStatus.MAX_ITERATIONS
                steps.append(step)
                return AgentResult(
                    agent_name=agent_name,
                    success=False,
                    final_answer=None,
                    steps=steps,
                    iterations_used=iteration + 1,
                    error_message=f"Presupuesto excedido (${accumulated_cost:.6f})",
                    confidence=0.0,
                )

            # ── ACT: ejecutar la skill ──
            if skill_name:
                step.status = AgentStatus.ACTING
                try:
                    skill_result = SkillOrchestrator.execute(
                        skill_name=skill_name,
                        params=step.skill_params or {},
                        context=context,
                    )
                    step.skill_result = skill_result.data if hasattr(skill_result, 'data') else {}
                    # Estimar costo de esta iteración (valores default si no hay log)
                    accumulated_cost += 0.0001  # ~$0.0001 por llamada DeepSeek
                except Exception as e:
                    logger.error(
                        f"[ReAct] {agent_name} error ejecutando "
                        f"skill '{skill_name}': {e}"
                    )
                    step.status = AgentStatus.FAILED
                    step.skill_result = {'error': str(e)}

            # ── OBSERVE: evaluar si el resultado es suficiente ──
            observation = self._observe(message, step, context)
            step.status = AgentStatus.OBSERVING
            steps.append(step)

            if observation.get('is_sufficient', False):
                logger.info(
                    f"[ReAct] {agent_name} resultado suficiente "
                    f"en iteraci\u00f3n {iteration}"
                )
                return AgentResult(
                    agent_name=agent_name,
                    success=True,
                    final_answer=observation.get('final_answer', step.skill_result),
                    steps=steps,
                    iterations_used=iteration + 1,
                    confidence=observation.get('confidence', 0.7),
                )

            # Actualizar mensaje con lo observado para la siguiente iteración
            message = self._build_next_message(message, step, observation)

        # ── Max iterations sin resultado satisfactorio ──
        logger.warning(
            f"[ReAct] {agent_name} alcanz\u00f3 m\u00e1ximo de "
            f"{self.definition.max_iterations} iteraciones sin resultado satisfactorio"
        )
        return AgentResult(
            agent_name=agent_name,
            success=False,
            final_answer=None,
            steps=steps,
            iterations_used=self.definition.max_iterations,
            error_message="max_iterations alcanzado sin resultado suficiente",
            confidence=0.0,
        )

    def _think(self, message: str, context: dict,
               steps: List[AgentStep]) -> dict:
        """
        El LLM decide la próxima acción.

        Returns:
            dict con keys: reasoning, skill_name (opcional), params (opcional),
                          is_final (bool), final_answer (opcional, si is_final),
                          confidence (float)
        """
        from ..services.llm import LLMService

        # Construir prompt con historial de pasos
        steps_context = ""
        if steps:
            steps_context = "\n".join([
                f"  Paso {s.iteration}: {s.thought} "
                f"→ skill={s.skill_used} "
                f"→ estado={s.status.value}"
                for s in steps[-3:]  # últimos 3 pasos
            ])

        prompt = self.definition.system_prompt + f"""

CONTEXTO ACTUAL:
Mensaje del usuario: {message}
{'Pasos anteriores:' if steps_context else ''}
{steps_context}

SKILLS DISPONIBLES:
{', '.join(self.definition.allowed_skills)}

Debes responder SOLO con un JSON válido en este formato:
{{
  "reasoning": "explica brevemente tu razonamiento",
  "is_final": true|false,
  "skill_name": "nombre_de_skill_si_no_es_final",
  "params": {{ "param1": "valor1" }} si aplica,
  "final_answer": {{ "respuesta": "..." }} si is_final=true,
  "confidence": 0.0 a 1.0
}}"""

        try:
            success, msg, response = LLMService._call_deepseek_api(
                messages=[{"role": "user", "content": message}],
                system_prompt=prompt,
            )
            if success and response:
                content = response.get('content', '')
                import json
                import re
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

    def _observe(self, original_message: str, step: AgentStep,
                 context: dict) -> dict:
        """
        Evalúa si el resultado de la skill es suficiente.

        Returns:
            dict con keys: is_sufficient (bool), final_answer (opcional),
                          confidence (float), feedback (str)
        """
        from ..services.llm import LLMService

        if not step.skill_result:
            return {'is_sufficient': False, 'confidence': 0.0,
                    'feedback': 'Sin resultado de skill'}

        prompt = f"""Evalúa si el siguiente resultado responde adecuadamente
la consulta del usuario.

Consulta original: {original_message}
Skill usada: {step.skill_used}
Resultado obtenido: {step.skill_result}

Responde SOLO con JSON:
{{
  "is_sufficient": true|false,
  "confidence": 0.0 a 1.0,
  "feedback": "explicación breve de por qué es o no suficiente"
}}"""

        try:
            success, msg, response = LLMService._call_deepseek_api(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="Eres un evaluador de calidad de respuestas.",
            )
            if success and response:
                content = response.get('content', '')
                import json
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    result = json.loads(json_match.group())
                    result['final_answer'] = step.skill_result
                    return result
        except Exception as e:
            logger.error(f"[ReAct] Error en _observe: {e}")

        # Si el resultado tiene datos, asumir suficiente
        has_data = bool(step.skill_result and (
            isinstance(step.skill_result, dict) and len(step.skill_result) > 0
        ))
        return {
            'is_sufficient': has_data,
            'confidence': 0.5 if has_data else 0.0,
            'feedback': 'evaluación falló, usando heurística',
            'final_answer': step.skill_result if has_data else None,
        }

    def _build_next_message(self, original_message: str,
                            last_step: AgentStep,
                            observation: dict) -> str:
        """Construye el mensaje para la siguiente iteración del ReAct loop."""
        return (
            f"Consulta original: {original_message}\n\n"
            f"Resultado anterior ({last_step.skill_used}): "
            f"{last_step.skill_result}\n\n"
            f"Evaluación: {observation.get('feedback', 'insuficiente')}\n\n"
            f"Por favor intenta con otra skill o ajusta los parámetros."
        )
