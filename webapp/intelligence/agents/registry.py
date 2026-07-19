"""
AgentRegistry — Registro central de agentes.

Mismo patrón que SkillRegistry (singleton, registro en apps.py).

SPEC: refactor_plataforma_agentes.md — Fase 2
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base_agent import AgentDefinition, BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Registry singleton de agentes.

    Los agentes se registran en apps.py (IntelligenceConfig.ready())
    junto con las skills existentes.
    """

    _instance: Optional['AgentRegistry'] = None
    _agents: Dict[str, BaseAgent] = {}

    def __new__(cls) -> 'AgentRegistry':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._agents = {}
        return cls._instance

    # ── Registro ─────────────────────────────────────────────────────────

    def register(self, agent: BaseAgent) -> None:
        """
        Registra un agente en el catálogo.

        Args:
            agent: Instancia de BaseAgent

        Raises:
            ValueError: Si el agente no tiene nombre o ya existe
        """
        name = agent.definition.name
        if not name:
            raise ValueError("Agente debe tener 'definition.name' definido")

        if name in self._agents:
            logger.warning(
                f"Agente '{name}' ya registrado. Reemplazando..."
            )

        self._agents[name] = agent
        logger.info(
            f"Agente registrado: '{name}' "
            f"(dominio: {agent.definition.domain}, "
            f"nivel: {agent.definition.access_level}, "
            f"skills: {len(agent.definition.allowed_skills)})"
        )

    # ── Búsqueda ─────────────────────────────────────────────────────────

    def get_by_name(self, name: str) -> Optional[BaseAgent]:
        """Obtiene un agente por su nombre único."""
        return self._agents.get(name)

    def list_available(
        self,
        user_level: int = 1,
        domain: Optional[str] = None,
    ) -> List[AgentDefinition]:
        """
        Lista agentes activos accesibles para un nivel de usuario.

        Args:
            user_level: Nivel de acceso del usuario (1-5)
            domain: Filtrar por dominio (opcional)

        Returns:
            Lista de AgentDefinition de agentes disponibles
        """
        return [
            a.definition for a in self._agents.values()
            if a.definition.is_active
            and a.definition.access_level <= user_level
            and (domain is None or a.definition.domain == domain)
        ]

    def list_all(self) -> List[dict]:
        """Lista todos los agentes registrados con su schema."""
        return [
            a.get_schema() for a in self._agents.values()
        ]

    # ── Control operacional ──────────────────────────────────────────────

    def deactivate(self, name: str) -> bool:
        """Desactiva un agente sin eliminarlo del registro."""
        agent = self._agents.get(name)
        if agent:
            agent.definition.is_active = False
            logger.info(f"Agente desactivado: '{name}'")
            return True
        return False

    def activate(self, name: str) -> bool:
        """Reactiva un agente desactivado."""
        agent = self._agents.get(name)
        if agent:
            agent.definition.is_active = True
            logger.info(f"Agente activado: '{name}'")
            return True
        return False

    # ── Estadísticas ─────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del registry."""
        total = len(self._agents)
        activos = sum(1 for a in self._agents.values() if a.definition.is_active)
        por_dominio: Dict[str, int] = {}
        for a in self._agents.values():
            d = a.definition.domain
            por_dominio[d] = por_dominio.get(d, 0) + 1

        return {
            'total': total,
            'activos': activos,
            'inactivos': total - activos,
            'por_dominio': por_dominio,
            'agentes': list(self._agents.keys()),
        }

    def clear(self) -> None:
        """Limpia todos los agentes registrados (útil para tests)."""
        self._agents.clear()
        logger.info("AgentRegistry limpiado")
