"""
Supervisor — Nodo raíz del grafo LangGraph.

El Supervisor no elige una skill — elige uno o más agentes.
Reutiliza el SemanticSkillRouter (embeddings E5 + templates) pero aplicado
a AgentDefinition.description en vez de a skills individuales.

SPEC: refactor_plataforma_agentes.md — Fase 3
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .registry import AgentRegistry
from ..services.semantic_router import SemanticSkillRouter, RoutingResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Templates del Supervisor (descripciones de agentes + ejemplos few-shot)
# ═══════════════════════════════════════════════════════════════════════════════
# Se usan con SemanticSkillRouter.classify() para determinar qué agente(s) activar
# ═══════════════════════════════════════════════════════════════════════════════

# Templates por defecto para el Supervisor
# Se genera automáticamente desde AgentDefinition.description de los agentes registrados
# más ejemplos few-shot para mejorar discriminación semántica

_DEFAULT_SUPERVISOR_TEMPLATES: Dict[str, List[str]] = {
    'agente_propiedades': [
        # Búsquedas directas de propiedades
        'busco departamento en Cayma',
        'quiero comprar una casa en Yanahuara',
        'necesito un terreno para construir',
        'busco propiedades en Cerro Colorado',
        'alquiler de departamentos en Sachaca',
        'busco casa en venta en Paucarpata',
        'muéstrame departamentos en José Luis Bustamante',
        'departamento amoblado en Yanahuara en alquiler',
        'casa con 3 dormitorios en Cayma',
        'terreno de 500 metros en Sachaca',
        # Análisis de propiedades
        'analiza esta propiedad como inversión',
        'qué rentabilidad tiene esta propiedad',
        'análisis de mercado para este inmueble',
        'compara estas dos propiedades',
    ],
    'agente_mercado': [
        # Análisis de mercado
        'cómo está el mercado en Cayma',
        'precio promedio de departamentos en Yanahuara',
        'tendencias de precios en Cerro Colorado',
        'comparativa de zonas residenciales',
        'cuál es el mejor distrito para invertir',
        'precio promedio de terrenos en Cayma',
        'dónde están subiendo los precios',
        # Marketing y campañas
        'qué campañas de Facebook están activas',
        'cómo están rindiendo los anuncios',
        'métricas de marketing del mes',
        'cuántos leads generamos este mes',
        'qué campaña está generando más leads',
        'ROI de las campañas de Meta Ads',
    ],
    'agente_requerimientos': [
        # Requerimientos
        'qué requerimientos tengo pendientes',
        'muéstreme los requerimientos activos',
        'quiero ver mis clientes buscando propiedad',
        'tengo un cliente que busca depa en Cayma',
        'recibí un mensaje de un cliente interesado',
        # Matching
        'cruza mis propiedades con requerimientos',
        'tengo matches nuevos',
        'qué matches tengo pendientes',
        'propiedades que match con mis clientes',
    ],
}

# Templates configurables desde settings
SUPERVISOR_TEMPLATES = None  # Se carga en __init__


class Supervisor:
    """
    Supervisor del sistema de agentes.

    Usa SemanticSkillRouter para clasificar consultas y determinar
    qué agente(s) activar. Reutiliza toda la infraestructura de embeddings
    E5 existente.

    La lógica de "Multi-Skill Orchestration" (detección de consultas
    compuestas) se reutiliza directamente de semantic_router.py.
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        threshold: Optional[float] = None,
    ):
        """
        Args:
            registry: AgentRegistry (usa singleton por defecto)
            threshold: Umbral de confianza para el routing semántico
        """
        self.registry = registry or AgentRegistry()
        self.threshold = threshold or 0.45

        # Inicializar router semántico con templates del Supervisor
        templates = self._build_templates()
        self.router = SemanticSkillRouter(threshold=self.threshold)
        # Sobrescribir templates con los del Supervisor
        self.router.templates = templates
        # Pre-calcular embeddings
        self.router.precompute_all_embeddings()

        logger.info(
            f"Supervisor inicializado: {len(templates)} agentes "
            f"({sum(len(v) for v in templates.values())} templates, "
            f"threshold={self.threshold})"
        )

    def _build_templates(self) -> Dict[str, List[str]]:
        """
        Construye templates del Supervisor desde los agentes registrados
        más ejemplos few-shot por defecto.

        Returns:
            Dict {agent_name: [templates]}
        """
        templates = {}

        # 1. Descripciones de agentes registrados
        for agent_def in self.registry.list_all():
            name = agent_def['name']
            desc = agent_def['description']
            # Usar la descripción como template base
            templates[name] = [desc]

        # 2. Sobrescribir con templates específicos (mejor discriminación)
        for name, examples in _DEFAULT_SUPERVISOR_TEMPLATES.items():
            if name in templates:
                # Mezclar: descripción + ejemplos
                existing = templates[name]
                templates[name] = existing + examples
            else:
                templates[name] = examples

        # 3. Agente fallback (siempre presente)
        if 'agente_fallback_rag' not in templates:
            templates['agente_fallback_rag'] = [
                'consulta general',
                'información del sistema',
                'ayuda',
                'quién eres',
                'cómo funciona esto',
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

        Reutiliza la lógica de Multi-Skill Orchestration (ya existente en
        SemanticSkillRouter) para detectar y descomponer consultas compuestas.

        Args:
            message: Mensaje del usuario
            user_level: Nivel de acceso del usuario
            user_context: Contexto adicional del usuario

        Returns:
            Dict con plan de ejecución:
            {
                'is_multi': bool,
                'execution_mode': 'single' | 'sequential' | 'parallel',
                'agents': [
                    {
                        'name': str,
                        'description': str,
                        'order': int,
                        'score': float,
                        'sub_query': str,
                    }
                ],
                'original_query': str,
                'latency_ms': float,
            }
        """
        start = time.time()

        if not message or not message.strip():
            return self._empty_plan(message)

        # ── 1. Detectar si es consulta compuesta ──
        is_compound = self.router._es_consulta_compuesta(message)

        if is_compound:
            # Descomponer y clasificar cada sub-consulta
            sub_queries = self.router._descomponer_consulta(message)
            agents = []
            for i, sq in enumerate(sub_queries):
                result = self.router.classify(sq, user_context)
                if result.accepted and result.skill_name:
                    agent_def = self._get_agent_def(result.skill_name)
                    if agent_def and agent_def.get('access_level', 1) <= user_level:
                        agents.append({
                            'name': result.skill_name,
                            'description': agent_def.get('description', ''),
                            'order': i + 1,
                            'score': result.score,
                            'sub_query': sq,
                        })

            if len(agents) >= 2:
                execution_mode = 'parallel'
            elif len(agents) == 1:
                execution_mode = 'single'
            else:
                execution_mode = 'single'
                agents = self._fallback_plan(message)

            elapsed = (time.time() - start) * 1000
            logger.info(
                f"[Supervisor] Consulta compuesta: {len(agents)} agente(s), "
                f"modo={execution_mode}, latencia={elapsed:.1f}ms"
            )

            return {
                'is_multi': len(agents) >= 2,
                'execution_mode': execution_mode,
                'agents': agents,
                'original_query': message,
                'latency_ms': round(elapsed, 2),
            }

        # ── 2. Consulta simple: clasificar contra agente ──
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
                    f"[Supervisor] Agente detectado: '{result.skill_name}' "
                    f"(score={result.score:.4f}, latencia={elapsed:.1f}ms)"
                )
                return {
                    'is_multi': False,
                    'execution_mode': 'single',
                    'agents': agents,
                    'original_query': message,
                    'latency_ms': round(elapsed, 2),
                }

        # ── 3. Fallback: RAG puro ──
        elapsed = (time.time() - start) * 1000
        plan = self._fallback_plan(message)
        plan['latency_ms'] = round(elapsed, 2)
        logger.info(
            f"[Supervisor] Fallback RAG (score={result.score:.4f}, "
            f"latencia={elapsed:.1f}ms)"
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
