"""
Sistema de Skills para Intelligence.

Módulos principales:
- skill_base: Clases base para skills
- orchestrator: Coordinación de ejecución
- registry: Registro dinámico de skills
- cache: Sistema de cache inteligente
- mcp_server: Exposición MCP para clientes externos
- examples: Skills de ejemplo
"""
from __future__ import annotations

__all__ = [
    'Skill', 'SkillResult', 'SkillParameter', 'SkillRegistry',
    'SkillOrchestrator', 'ExecutionContext', 'ExecutionMetrics',
    'SkillPipelineStep', 'SkillPipelineResult',
    'DynamicSkillRegistry', 'SkillCache',
    'create_skill_system',
]


def _lazy_import(name: str):
    if name in {'Skill', 'SkillResult', 'SkillParameter', 'SkillRegistry'}:
        from ..services.skill_base import (
            Skill, SkillResult, SkillParameter, SkillRegistry
        )
        return locals()[name]

    if name == 'SkillOrchestrator':
        from .orchestrator import SkillOrchestrator
        return SkillOrchestrator

    if name == 'ExecutionContext':
        from .orchestrator import ExecutionContext
        return ExecutionContext

    if name == 'ExecutionMetrics':
        from .orchestrator import ExecutionMetrics
        return ExecutionMetrics

    if name == 'SkillPipelineStep':
        from .orchestrator import SkillPipelineStep
        return SkillPipelineStep

    if name == 'SkillPipelineResult':
        from .orchestrator import SkillPipelineResult
        return SkillPipelineResult

    if name == 'DynamicSkillRegistry':
        from .registry import SkillRegistry as DynamicSkillRegistry
        return DynamicSkillRegistry

    if name == 'SkillCache':
        from .cache import SkillCache
        return SkillCache

    if name == 'MCPSkillServer':
        try:
            from .mcp_server import MCPSkillServer
            return MCPSkillServer
        except ImportError as e:
            raise AttributeError(f"{name} is not available: {e}") from e

    if name == 'create_mcp_server':
        try:
            from .mcp_server import create_mcp_server
            return create_mcp_server
        except ImportError as e:
            raise AttributeError(f"{name} is not available: {e}") from e

    raise AttributeError(f"module {__name__} has no attribute {name}")


def __getattr__(name: str):
    return _lazy_import(name)


def __dir__():
    return sorted(__all__)


def create_skill_system(
    redis_url: str = "redis://localhost:6379/0",
    enable_cache: bool = True,
    auto_discover_skills: bool = True,
    auto_discover_examples: bool = True,
) -> SkillOrchestrator:
    """
    Crea un sistema completo de skills listo para usar.

    Args:
        redis_url: URL de Redis para cache
        enable_cache: Si habilitar cache
        auto_discover_skills: Si cargar skills del paquete de skills automáticamente
        auto_discover_examples: Si cargar skills de ejemplo automáticamente

    Returns:
        SkillOrchestrator configurado y listo
    """
    from .registry import SkillRegistry as DynamicSkillRegistry
    from .cache import SkillCache
    from .orchestrator import SkillOrchestrator

    # Crear registry
    registry = DynamicSkillRegistry()

    # Crear cache
    cache = SkillCache(redis_url=redis_url) if enable_cache else None

    # Crear orchestrator
    orchestrator = SkillOrchestrator(registry, cache)

    # Auto-discover skills avanzadas y ejemplos
    if auto_discover_skills:
        try:
            registry.discover_skills("intelligence.skills")
        except Exception as e:
            from ..services.metrics import log
            log.warning(f"No se pudieron cargar skills desde intelligence.skills: {e}")

    if auto_discover_examples:
        try:
            registry.discover_skills("intelligence.skills.examples")
        except Exception as e:
            from ..services.metrics import log
            log.warning(f"No se pudieron cargar skills de ejemplo: {e}")

    return orchestrator
