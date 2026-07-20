"""
Supervisor — Nodo raíz del grafo LangGraph.
SPEC: supervisor_llm_routing.md

El Supervisor elige agente(s) mediante FUNCTION CALLING del LLM (DeepSeek)
en vez de similitud de embeddings. El LLM recibe la lista de agentes como
tools/herramientas y decide cuál(es) invocar, con razonamiento explícito.

Si DeepSeek falla (timeout, error), degrada a fallback por embeddings E5
usando el SemanticSkillRouter existente.

SPEC: refactor_plataforma_agentes.md — Fase 3 (actualizado)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .registry import AgentRegistry
from ..services.semantic_router import SemanticSkillRouter, RoutingResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Descripciones de agentes por INTENCIÓN (no por similitud léxica)
# ═══════════════════════════════════════════════════════════════════════════════
# Reemplazan los templates E5 del Supervisor.
# Describen CUÁNDO usar cada agente basado en la intención del usuario.
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_DESCRIPTIONS: Dict[str, str] = {
    "agente_propiedades": (
        "Busca o consulta el INVENTARIO EXISTENTE de propiedades: qué propiedades hay, "
        "disponibilidad, características, ubicación, matching entre oferta y requerimientos. "
        "Úsalo cuando el usuario pregunta qué tiene la empresa, busca algo específico, "
        "o quiere ver listados. Ejemplos de intención (no frases literales): "
        "'qué tienes', 'busco', 'muéstrame', 'tienen algo de'."
    ),
    "agente_mercado": (
        "Genera ANÁLISIS y REPORTES de mercado: precios promedio, evolución histórica de precios, "
        "tendencias por zona, estado de campañas de marketing. NO se usa para listar propiedades "
        "existentes, sino para responder preguntas de tipo analítico. "
        "Ejemplos de intención: 'cuál es el precio promedio', 'cómo ha evolucionado', "
        "'dame un reporte de', 'qué campañas están activas'."
    ),
    "agente_requerimientos": (
        "Gestiona los requerimientos de clientes/compradores y su cruce con el inventario. "
        "Úsalo cuando la consulta es sobre lo que un cliente busca, no sobre el inventario en sí."
    ),
}

# Templates para fallback por embeddings (mismos que antes)
_DEFAULT_SUPERVISOR_TEMPLATES: Dict[str, List[str]] = {
    'agente_propiedades': [
        'busco departamento en Cayma',
        'necesito un terreno para construir',
        'muéstrame departamentos en José Luis Bustamante',
        'terreno de 500 metros en Sachaca',
        'analiza esta propiedad como inversión',
        'qué rentabilidad tiene esta propiedad',
        'compara estas dos propiedades',
        'busco propiedades en arequipa',
        'quiero ver las propiedades disponibles',
        'lista de propiedades en venta',
        'departamentos disponibles en cayma',
        'terrenos en cayma para construir',
        'qué terrenos tienes disponibles',
        'muéstrame terrenos en cayma',
    ],
    'agente_mercado': [
        'cómo está el mercado en Cayma',
        'precio promedio de departamentos en Yanahuara',
        'tendencias de precios en Cerro Colorado',
        'comparativa de zonas residenciales',
        'cuál es el mejor distrito para invertir',
        'dónde están subiendo los precios',
        'qué campañas de Facebook están activas',
        'métricas de marketing del mes',
        'cuántos leads generamos este mes',
        'ROI de las campañas de Meta Ads',
        'tendencias del mercado inmobiliario',
        'evolución de precios en arequipa',
    ],
    'agente_requerimientos': [
        'qué requerimientos tengo pendientes',
        'muéstreme los requerimientos activos',
        'quiero ver mis clientes buscando propiedad',
        'tengo un cliente que busca depa en Cayma',
        'cruza mis propiedades con requerimientos',
        'tengo matches nuevos',
        'qué matches tengo pendientes',
        'propiedades que match con mis clientes',
    ],
}

# Templates configurables desde settings
SUPERVISOR_TEMPLATES = None


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers para construir herramientas del Supervisor
# ═══════════════════════════════════════════════════════════════════════════════


def build_supervisor_tools(available_agents: List[Dict[str, Any]]) -> List[dict]:
    """
    Convierte agentes disponibles en formato tools de OpenAI/DeepSeek.

    SPEC: supervisor_llm_routing.md — Sección 2.1.
    Usa AGENT_DESCRIPTIONS (por intención) en vez de descripciones genéricas.
    """
    tools = []
    for agent in available_agents:
        name = agent['name']
        desc = AGENT_DESCRIPTIONS.get(name, agent.get('description', ''))
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sub_query": {
                            "type": "string",
                            "description": (
                                "La parte del mensaje del usuario que este agente "
                                "debe resolver. Si el mensaje completo aplica, "
                                "repítelo tal cual."
                            ),
                        }
                    },
                    "required": ["sub_query"],
                },
            },
        })
    return tools


class Supervisor:
    """
    Supervisor del sistema de agentes.

    SPEC: supervisor_llm_routing.md.

    Usa FUNCTION CALLING de DeepSeek (tools) para elegir el agente,
    con razonamiento explícito del LLM. El routing por embeddings
    (SemanticSkillRouter) se mantiene como fallback si DeepSeek falla.

    La detección de consultas compuestas la resuelve el LLM naturalmente
    (puede llamar a múltiples herramientas en una respuesta), eliminando
    la necesidad de _es_consulta_compuesta y _descomponer_consulta.
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        threshold: Optional[float] = None,
    ):
        """
        Args:
            registry: AgentRegistry (usa singleton por defecto)
            threshold: Umbral de confianza para fallback por embeddings
        """
        self.registry = registry or AgentRegistry()
        self.threshold = threshold or 0.45

        # Inicializar router semántico SOLO para fallback
        templates = self._build_templates()
        self.router = SemanticSkillRouter(threshold=self.threshold)
        self.router.templates = templates
        self.router.precompute_all_embeddings()

        logger.info(
            f"Supervisor LLM inicializado: {len(templates)} agentes disponibles, "
            f"fallback por embeddings con {sum(len(v) for v in templates.values())} templates"
        )

    def _build_templates(self) -> Dict[str, List[str]]:
        """Construye templates solo para fallback por embeddings."""
        templates = {}
        for agent_def in self.registry.list_all():
            name = agent_def['name']
            desc = agent_def.get('description', '')
            templates[name] = [desc]
        for name, examples in _DEFAULT_SUPERVISOR_TEMPLATES.items():
            if name in templates:
                existing = templates[name]
                templates[name] = existing + examples
            else:
                templates[name] = examples
        if 'agente_fallback_rag' not in templates:
            templates['agente_fallback_rag'] = [
                'consulta general', 'información del sistema',
                'ayuda', 'quién eres', 'cómo funciona esto',
            ]
        return templates

    # ── Routing principal ──────────────────────────────────────────────

    def route(
        self,
        message: str,
        user_level: int = 1,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Determina qué agente(s) activar para una consulta.

        PRIMARIO: LLM function calling (DeepSeek con tools).
        FALLBACK: SemanticSkillRouter por embeddings.

        Args:
            message: Mensaje del usuario
            user_level: Nivel de acceso del usuario
            user_context: Contexto adicional del usuario

        Returns:
            Dict con plan de ejecución (mismo formato que antes):
            {
                'routing_method': 'llm' | 'embeddings_fallback',
                'reasoning': str,           # ← NUEVO: razonamiento del LLM
                'is_multi': bool,
                'execution_mode': 'single' | 'parallel',
                'agents': [{'name', 'description', 'order', 'score', 'sub_query'}],
                'original_query': str,
                'latency_ms': float,
            }
        """
        start = time.time()

        if not message or not message.strip():
            return self._empty_plan(message)

        # ── 1. Intentar routing por LLM ──
        try:
            return self._route_with_llm(message, user_level, user_context, start)
        except Exception as e:
            logger.warning(
                f"[Supervisor] LLM routing falló: {e}. "
                f"Usando fallback por embeddings."
            )
            return self._route_with_embeddings_fallback(
                message, user_level, user_context, start
            )

    def _route_with_llm(
        self, message: str, user_level: int,
        user_context: Optional[Dict], start: float,
    ) -> Dict[str, Any]:
        """
        Routing por LLM function calling.

        SPEC: supervisor_llm_routing.md — Sección 2.3.
        """
        from ..services.llm import LLMService

        # Agentes disponibles según nivel de usuario
        available = self.list_available_agents(user_level)
        if not available:
            plan = self._fallback_plan(message)
            plan['latency_ms'] = round((time.time() - start) * 1000, 2)
            return plan

        tools = build_supervisor_tools(available)

        result = LLMService.call_with_tools(
            system_prompt=(
                "Eres el supervisor de un sistema inmobiliario. Tu única tarea es decidir "
                "qué agente(s) deben resolver la consulta del usuario. "
                "Cada agente en la lista de herramientas tiene una descripción que indica "
                "CUÁNDO debe ser usado. "
                "Si la consulta tiene más de una intención distinta (ej. buscar propiedades "
                "Y pedir análisis de precios), llama a más de un agente, cada uno con su "
                "sub_query correspondiente. "
                "No inventes agentes que no estén en la lista de herramientas."
            ),
            message=message,
            tools=tools,
        )

        if not result.success or not result.tool_calls:
            logger.warning(
                f"[Supervisor] LLM no devolvió tool_calls válidos. "
                f"Usando fallback por embeddings."
            )
            return self._route_with_embeddings_fallback(
                message, user_level, user_context, start
            )

        elapsed = (time.time() - start) * 1000
        agents = []
        for tc in result.tool_calls:
            name = tc['name']
            sub_query = tc['arguments'].get('sub_query', message)
            agent_def = self._get_agent_def(name)
            if agent_def and agent_def.get('access_level', 1) <= user_level:
                agents.append({
                    'name': name,
                    'description': agent_def.get('description', ''),
                    'order': len(agents) + 1,
                    'score': 1.0,
                    'sub_query': sub_query,
                })

        if not agents:
            logger.warning(
                f"[Supervisor] LLM eligió agentes sin acceso. "
                f"Usando fallback por embeddings."
            )
            return self._route_with_embeddings_fallback(
                message, user_level, user_context, start
            )

        execution_mode = 'parallel' if len(agents) >= 2 else 'single'

        logger.info(
            f"[Supervisor] LLM routing: {len(agents)} agente(s), "
            f"modo={execution_mode}, latencia={elapsed:.1f}ms, "
            f"razonamiento='{result.reasoning[:80] if result.reasoning else 'N/A'}...'"
        )

        return {
            'routing_method': 'llm',
            'reasoning': result.reasoning,
            'is_multi': len(agents) >= 2,
            'execution_mode': execution_mode,
            'agents': agents,
            'original_query': message,
            'latency_ms': round(elapsed, 2),
        }

    def _route_with_embeddings_fallback(
        self, message: str, user_level: int,
        user_context: Optional[Dict], start: float,
    ) -> Dict[str, Any]:
        """
        Fallback: routing por embeddings E5 (SemanticSkillRouter).

        SPEC: supervisor_llm_routing.md — Sección 2.4.
        Reutiliza el sistema de templates anterior exactamente como estaba.
        """
        result = self.router.classify(message, user_context)

        if result.accepted and result.skill_name:
            agent_def = self._get_agent_def(result.skill_name)
            if agent_def and agent_def.get('access_level', 1) <= user_level:
                agents = [{
                    'name': result.skill_name,
                    'description': agent_def.get('description', ''),
                    'order': 1,
                    'score': result.score,
                    'sub_query': message,
                }]
                elapsed = (time.time() - start) * 1000
                logger.info(
                    f"[Supervisor] Fallback embeddings: '{result.skill_name}' "
                    f"(score={result.score:.4f}, latencia={elapsed:.1f}ms)"
                )
                return {
                    'routing_method': 'embeddings_fallback',
                    'reasoning': f"Fallback por embeddings: score={result.score:.4f}",
                    'is_multi': False,
                    'execution_mode': 'single',
                    'agents': agents,
                    'original_query': message,
                    'latency_ms': round(elapsed, 2),
                }

        # Fallback final: RAG puro
        elapsed = (time.time() - start) * 1000
        plan = self._fallback_plan(message)
        plan['latency_ms'] = round(elapsed, 2)
        plan['routing_method'] = 'embeddings_fallback'
        plan['reasoning'] = 'Ningún agente匹配, usando fallback RAG'
        logger.info(
            f"[Supervisor] Fallback embeddings -> RAG puro "
            f"(score={result.score:.4f}, latencia={elapsed:.1f}ms)"
        )
        return plan

    # ── Fallback ───────────────────────────────────────────────────────

    def _fallback_plan(self, message: str) -> Dict[str, Any]:
        """Plan de fallback cuando no se detecta ningún agente."""
        return {
            'is_multi': False,
            'execution_mode': 'single',
            'agents': [{
                'name': 'agente_fallback_rag',
                'description': 'Agente de respaldo para consultas generales',
                'order': 1,
                'score': 0.0,
                'sub_query': message,
            }],
            'original_query': message,
        }

    def _empty_plan(self, message: str) -> Dict[str, Any]:
        """Plan vacío para mensajes sin contenido."""
        return {
            'is_multi': False,
            'execution_mode': 'single',
            'agents': [],
            'original_query': message,
            'latency_ms': 0.0,
        }

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_agent_def(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Obtiene la definición de un agente por nombre."""
        for agent_schema in self.registry.list_all():
            if agent_schema['name'] == agent_name:
                return agent_schema
        return None

    def list_available_agents(self, user_level: int = 1) -> List[dict]:
        """Lista agentes disponibles para un nivel de usuario."""
        return [
            {
                'name': a['name'],
                'description': a['description'],
                'access_level': a['access_level'],
                'domain': a.get('domain', 'general'),
            }
            for a in self.registry.list_all()
            if a['is_active'] and a['access_level'] <= user_level
        ]

    @property
    def stats(self) -> Dict[str, Any]:
        """Estadísticas del Supervisor."""
        return {
            'threshold': self.threshold,
            'n_agents': len(self.router.templates),
            'n_templates': sum(len(v) for v in self.router.templates.values()),
            'router_stats': self.router.stats,
        }
