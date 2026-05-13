"""
BaseSkill — Clase abstracta base para todas las skills del sistema.

Toda skill debe implementar este contrato para ser registrable en el SkillRegistry.
Atributos requeridos: name, description, category, access_level, parameters_schema
Métodos requeridos: execute(), validate_params()
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── SkillResult ──────────────────────────────────────────────────────────────

@dataclass
class SkillResult:
    """
    Resultado estandarizado de una skill.

    Toda skill retorna un SkillResult. Esto permite que el agente formatee
    la respuesta de forma consistente sin saber qué hizo la skill internamente.
    """
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    skill_name: str = ""

    @classmethod
    def ok(
        cls,
        data: Any,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        skill_name: str = ""
    ) -> 'SkillResult':
        """Crea un resultado exitoso."""
        return cls(
            success=True,
            data=data,
            message=message,
            metadata=metadata or {},
            skill_name=skill_name
        )

    @classmethod
    def error(
        cls,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        skill_name: str = ""
    ) -> 'SkillResult':
        """Crea un resultado con error."""
        return cls(
            success=False,
            data=None,
            message=message,
            metadata=metadata or {},
            skill_name=skill_name
        )

    # ── Alias de compatibilidad con SkillResult LEGACY ──

    @property
    def error_message(self) -> Optional[str]:
        """Alias de 'message' para compatibilidad con código que usa SkillResult LEGACY."""
        return self.message if not self.success else None

    @classmethod
    def from_error(cls, error: str, **metadata) -> 'SkillResult':
        """
        Alias de compatibilidad con SkillResult LEGACY.
        Equivalente a SkillResult.error(message=error, metadata=metadata).
        """
        return cls(
            success=False,
            data=None,
            message=error,
            metadata=metadata,
        )


# ── BaseSkill ────────────────────────────────────────────────────────────────

class BaseSkill(ABC):
    """
    Clase base abstracta para todas las skills del sistema.

    Atributos de clase (definir en subclases):
        name (str): Identificador único en snake_case. Ej: 'busqueda_propiedades'
        description (str): Descripción en lenguaje natural para que el agente elija la skill
        category (str): Categoría: busqueda | crm | reporte | notificacion | template | custom
        access_level (int): Nivel mínimo de acceso (1, 2 o 3)
        is_active (bool): Si la skill está disponible para el agente
        parameters_schema (dict): Schema de parámetros que acepta la skill
    """

    # ── Atributos de clase (sobrescribir en subclases) ──
    name: str = ""
    description: str = ""
    category: str = "custom"
    access_level: int = 1
    is_active: bool = True
    parameters_schema: Dict[str, Dict[str, Any]] = {}

    def __init_subclass__(cls, **kwargs):
        """Validación automática al definir subclases."""
        super().__init_subclass__(**kwargs)
        if not cls.name:
            raise ValueError(
                f"Skill '{cls.__name__}' debe definir 'name' (snake_case único)"
            )
        if not cls.description:
            raise ValueError(
                f"Skill '{cls.__name__}' debe definir 'description'"
            )
        if cls.category not in ('busqueda', 'crm', 'reporte', 'notificacion', 'template', 'custom'):
            logger.warning(
                f"Skill '{cls.name}' tiene categoría '{cls.category}' no estándar. "
                f"Usar: busqueda, crm, reporte, notificacion, template, custom"
            )
        if not isinstance(cls.parameters_schema, dict):
            raise ValueError(
                f"Skill '{cls.__name__}' parameters_schema debe ser un dict"
            )

    # ── Métodos abstractos ──

    @abstractmethod
    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        """
        Ejecuta la skill con los parámetros extraídos.

        Args:
            params: Diccionario con parámetros validados según parameters_schema
            context: Contexto opcional del usuario (nivel, perfil, etc.)

        Returns:
            SkillResult con el resultado estandarizado
        """
        ...

    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Valida que los parámetros recibidos son suficientes para ejecutar.

        Args:
            params: Diccionario con parámetros a validar

        Returns:
            True si los parámetros son válidos, False en caso contrario
        """
        ...

    # ── Métodos concretos ──

    def get_schema(self) -> Dict[str, Any]:
        """Retorna el schema completo de la skill para el agente."""
        return {
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'access_level': self.access_level,
            'is_active': self.is_active,
            'parameters_schema': self.parameters_schema,
        }

    def can_user_access(self, user_level: int) -> bool:
        """Verifica si un usuario con cierto nivel puede usar esta skill."""
        return self.is_active and user_level >= self.access_level

    def get_parameter_schema(self) -> Dict[str, Dict[str, Any]]:
        """
        Retorna el schema de parámetros para documentación/API.
        Compatibilidad con Skill LEGACY.
        """
        return self.parameters_schema
