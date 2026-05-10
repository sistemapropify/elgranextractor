"""
Base classes para el sistema de Skills.

Una Skill es una capacidad autónoma que:
- Tiene nombre, descripción y parámetros definidos
- Puede ejecutarse independientemente del chat
- Devuelve resultados estandarizados
- Es reutilizable desde diferentes contextos (web, API, MCP, CLI)
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class SkillParameter:
    """Definición de un parámetro de skill."""
    name: str
    type: str  # 'str', 'int', 'float', 'bool', 'list', 'dict'
    description: str
    required: bool = True
    default: Any = None
    options: Optional[List[str]] = None  # Para parámetros con opciones fijas


@dataclass
class SkillResult:
    """Resultado estandarizado de una skill."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def error(self) -> Optional[str]:
        """Alias para error_message para compatibilidad."""
        return self.error_message

    @classmethod
    def ok(cls, data: Dict[str, Any], **metadata) -> 'SkillResult':
        """Resultado exitoso."""
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def from_error(cls, error: str, **metadata) -> 'SkillResult':
        """Resultado con error."""
        return cls(success=False, error_message=error, metadata=metadata)


class Skill(ABC):
    """
    Clase base para todas las skills del sistema.

    Una skill debe definir:
    - name: identificador único
    - description: descripción semántica para el LLM
    - parameters: parámetros de entrada con tipos
    - execute(): lógica de ejecución
    """

    # Definir en subclases
    name: str = ""
    description: str = ""
    parameters: Dict[str, SkillParameter] = {}

    def __init_subclass__(cls, **kwargs):
        """Validación automática al definir subclases."""
        super().__init_subclass__(**kwargs)
        if not cls.name:
            raise ValueError(f"Skill {cls.__name__} debe definir 'name'")
        if not cls.description:
            raise ValueError(f"Skill {cls.__name__} debe definir 'description'")
        if not isinstance(cls.parameters, dict):
            raise ValueError(f"Skill {cls.__name__} parameters debe ser dict")

    @abstractmethod
    def execute(self, **kwargs) -> SkillResult:
        """
        Ejecuta la skill con los parámetros proporcionados.

        Args:
            **kwargs: Parámetros según self.parameters

        Returns:
            SkillResult con el resultado o error
        """
        pass

    def validate_params(self, **kwargs) -> Dict[str, Any]:
        """
        Valida y convierte parámetros según la definición.

        Raises:
            ValueError: Si faltan parámetros requeridos o tipos inválidos
        """
        validated = {}

        # Verificar parámetros requeridos
        for param_name, param_def in self.parameters.items():
            if param_name not in kwargs and param_def.required:
                raise ValueError(f"Parámetro requerido faltante: {param_name}")

            value = kwargs.get(param_name, param_def.default)
            if value is None and param_def.required:
                raise ValueError(f"Parámetro requerido faltante: {param_name}")

            # Validar tipo básico
            if value is not None:
                validated[param_name] = self._convert_type(value, param_def.type)

        return validated

    def _convert_type(self, value: Any, expected_type: str) -> Any:
        """Convierte valor al tipo esperado."""
        if expected_type == 'str':
            return str(value)
        elif expected_type == 'int':
            return int(value)
        elif expected_type == 'float':
            return float(value)
        elif expected_type == 'bool':
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'si')
            return bool(value)
        elif expected_type == 'list':
            return list(value) if isinstance(value, (list, tuple)) else [value]
        elif expected_type == 'dict':
            return dict(value) if isinstance(value, dict) else {'value': value}
        else:
            return value  # Tipo desconocido, devolver como está

    def get_parameter_schema(self) -> Dict[str, Dict[str, Any]]:
        """Retorna el schema de parámetros para documentación/API."""
        return {
            name: {
                'type': param.type,
                'description': param.description,
                'required': param.required,
                'default': param.default,
                'options': param.options,
            }
            for name, param in self.parameters.items()
        }


class SkillRegistry:
    """
    Registry global de skills disponibles.

    Permite registrar skills y buscarlas por nombre o descripción.
    """

    _skills: Dict[str, Skill] = {}

    @classmethod
    def register(cls, skill_class: type) -> None:
        """Registra una skill en el registry."""
        if not issubclass(skill_class, Skill):
            raise ValueError(f"{skill_class} no es una subclase de Skill")

        skill_instance = skill_class()
        cls._skills[skill_instance.name] = skill_instance

    @classmethod
    def get_skill(cls, name: str) -> Optional[Skill]:
        """Obtiene una skill por nombre."""
        return cls._skills.get(name)

    @classmethod
    def list_skills(cls) -> Dict[str, Dict[str, Any]]:
        """Lista todas las skills registradas con metadata."""
        return {
            name: {
                'description': skill.description,
                'parameters': skill.get_parameter_schema(),
            }
            for name, skill in cls._skills.items()
        }

    @classmethod
    def find_skills_by_description(cls, query: str) -> List[Skill]:
        """
        Busca skills cuya descripción contenga la query (case-insensitive).
        Útil para matching semántico básico.
        """
        query_lower = query.lower()
        return [
            skill for skill in cls._skills.values()
            if query_lower in skill.description.lower()
        ]


# ── Skills de ejemplo (para testing) ────────────────────────────────────────

class ExampleSkill(Skill):
    """Skill de ejemplo que suma dos números."""

    name = "suma_numeros"
    description = "Suma dos números y retorna el resultado"
    parameters = {
        'a': SkillParameter(
            name='a',
            type='int',
            description='Primer número a sumar',
            required=True
        ),
        'b': SkillParameter(
            name='b',
            type='int',
            description='Segundo número a sumar',
            required=True
        ),
    }

    def execute(self, **kwargs) -> SkillResult:
        try:
            params = self.validate_params(**kwargs)
            result = params['a'] + params['b']
            return SkillResult.ok(
                data={'resultado': result},
                operation='suma',
                inputs=params
            )
        except Exception as e:
            return SkillResult.from_error(str(e))