"""
Skill Registry Dinámico.

Sistema de registro y discovery automático de skills.
Permite cargar skills dinámicamente desde paquetes y directorios.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
from typing import Dict, Any, List, Optional, Type
from pathlib import Path


class SkillRegistry:
    """
    Registry dinámico de skills disponibles.

    Características:
    - Discovery automático de skills en paquetes
    - Metadata completa de skills
    - Búsqueda semántica
    - Versionado y hot-reload
    - Validación de skills al registro
    """

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._skill_classes: Dict[str, Type[Skill]] = {}

    def register_skill(self, skill_class: Type[Skill]) -> None:
        """
        Registra una skill con validación completa.

        Args:
            skill_class: Clase de la skill a registrar

        Raises:
            ValueError: Si la skill no es válida
        """
        from ..services.skill_base import Skill
        from ..services.metrics import log

        # Validar que es una subclase de Skill
        if not inspect.isclass(skill_class) or not issubclass(skill_class, Skill):
            raise ValueError(f"{skill_class} no es una subclase de Skill")

        # Validar atributos requeridos
        if not hasattr(skill_class, 'name') or not skill_class.name:
            raise ValueError(f"Skill {skill_class.__name__} debe definir 'name'")

        if not hasattr(skill_class, 'description') or not skill_class.description:
            raise ValueError(f"Skill {skill_class.__name__} debe definir 'description'")

        # Verificar que no existe ya
        if skill_class.name in self._skills:
            log.warning(f"Skill '{skill_class.name}' ya registrada, reemplazando")
            # Podríamos permitir override o rechazar

        # Crear instancia para validación
        try:
            skill_instance = skill_class()
        except Exception as e:
            raise ValueError(f"No se pudo instanciar skill {skill_class.__name__}: {e}")

        # Validar parámetros (solo estructura, no valores)
        try:
            self._validate_skill_structure(skill_instance)
        except Exception as e:
            raise ValueError(f"Estructura inválida en skill {skill_class.__name__}: {e}")

        # Registrar
        self._skills[skill_class.name] = skill_instance
        self._skill_classes[skill_class.name] = skill_class
        self._metadata[skill_class.name] = self._extract_metadata(skill_class, skill_instance)

        log.info(f"Skill registrada: {skill_class.name}")

    def discover_skills(self, package_path: str) -> int:
        """
        Descubre y registra skills automáticamente desde un paquete.

        Args:
            package_path: Path del paquete (ej: "intelligence.skills.examples")

        Returns:
            Número de skills registradas
        """
        from ..services.metrics import log
        from ..services.skill_base import Skill

        registered_count = 0

        try:
            # Importar el paquete
            package = importlib.import_module(package_path)

            # Iterar sobre módulos en el paquete
            if hasattr(package, '__path__'):
                for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
                    full_modname = f"{package_path}.{modname}"

                    try:
                        # Importar módulo
                        module = importlib.import_module(full_modname)

                        # Buscar clases de skills en el módulo
                        for name, obj in inspect.getmembers(module):
                            if (inspect.isclass(obj) and
                                issubclass(obj, Skill) and
                                obj != Skill):  # No registrar la clase base

                                try:
                                    self.register_skill(obj)
                                    registered_count += 1
                                except ValueError as e:
                                    log.warning(f"Error registrando skill {name}: {e}")

                    except ImportError as e:
                        log.warning(f"Error importando módulo {full_modname}: {e}")

        except ImportError as e:
            log.error(f"Error importando paquete {package_path}: {e}")

        log.info(f"Discovery completado: {registered_count} skills registradas desde {package_path}")
        return registered_count

    def discover_skills_from_directory(self, directory_path: str) -> int:
        """
        Descubre skills desde un directorio de archivos Python.

        Args:
            directory_path: Path absoluto del directorio

        Returns:
            Número de skills registradas
        """
        from ..services.metrics import log
        from ..services.skill_base import Skill

        registered_count = 0
        directory = Path(directory_path)

        if not directory.exists() or not directory.is_dir():
            log.error(f"Directorio no existe: {directory_path}")
            return 0

        # Buscar archivos .py
        for py_file in directory.glob("*.py"):
            if py_file.name.startswith("__"):
                continue

            try:
                # Importar como módulo
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Buscar skills en el módulo
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and
                            issubclass(obj, Skill) and
                            obj != Skill):

                            try:
                                self.register_skill(obj)
                                registered_count += 1
                            except ValueError as e:
                                log.warning(f"Error registrando skill {name}: {e}")

            except Exception as e:
                log.warning(f"Error procesando archivo {py_file}: {e}")

        log.info(f"Discovery desde directorio completado: {registered_count} skills desde {directory_path}")
        return registered_count

    def get_skill(self, name: str) -> Optional[Skill]:
        """
        Obtiene instancia de skill por nombre.

        Args:
            name: Nombre de la skill

        Returns:
            Instancia de skill o None si no existe
        """
        return self._skills.get(name)

    def get_skill_class(self, name: str) -> Optional[Type[Skill]]:
        """
        Obtiene clase de skill por nombre.

        Args:
            name: Nombre de la skill

        Returns:
            Clase de skill o None si no existe
        """
        return self._skill_classes.get(name)

    def get_skill_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información completa de una skill.

        Args:
            name: Nombre de la skill

        Returns:
            Dict con metadata o None si no existe
        """
        return self._metadata.get(name)

    def list_skills(self) -> List[Dict[str, Any]]:
        """
        Lista todas las skills registradas con metadata.

        Returns:
            Lista de dicts con información de skills
        """
        return list(self._metadata.values())

    def search_skills(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Búsqueda semántica de skills por descripción.

        Args:
            query: Texto a buscar
            limit: Máximo número de resultados

        Returns:
            Lista de skills que coinciden
        """
        query_lower = query.lower()
        query_tokens = re.findall(r"\b[\wáéíóúñü]+\b", query_lower)
        matches = []

        for metadata in self._metadata.values():
            description = metadata.get('description', '').lower()
            name = metadata.get('name', '').lower()

            if query_lower in description or query_lower in name:
                matches.append(metadata)
                continue

            if any(
                token in description or token in name
                for token in query_tokens
                if len(token) >= 3
            ):
                matches.append(metadata)

        # Ordenar por relevancia (más coincidencias primero)
        matches.sort(key=lambda x: (
            query_lower in x.get('name', '').lower(),
            len(x.get('description', ''))
        ), reverse=True)

        return matches[:limit]

    def unregister_skill(self, name: str) -> bool:
        """
        Remueve una skill del registry.

        Args:
            name: Nombre de la skill

        Returns:
            True si se removió, False si no existía
        """
        if name in self._skills:
            del self._skills[name]
            del self._skill_classes[name]
            del self._metadata[name]
            log.info(f"Skill removida: {name}")
            return True
        return False

    def reload_skill(self, name: str) -> bool:
        """
        Recarga una skill (útil para desarrollo).

        Args:
            name: Nombre de la skill

        Returns:
            True si se recargó exitosamente
        """
        skill_class = self._skill_classes.get(name)
        if not skill_class:
            return False

        try:
            # Re-registrar (esto reemplaza la instancia)
            self.register_skill(skill_class)
            log.info(f"Skill recargada: {name}")
            return True
        except Exception as e:
            log.error(f"Error recargando skill {name}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Estadísticas del registry.

        Returns:
            Dict con estadísticas
        """
        return {
            'total_skills': len(self._skills),
            'skill_names': list(self._skills.keys()),
            'skills_by_category': self._count_by_category(),
        }

    def _extract_metadata(self, skill_class: Type[Skill], skill_instance: Skill) -> Dict[str, Any]:
        """Extrae metadata completa de una skill."""
        return {
            'name': skill_class.name,
            'description': skill_class.description,
            'class_name': skill_class.__name__,
            'module': skill_class.__module__,
            'parameters': skill_instance.get_parameter_schema(),
            'required_permissions': getattr(skill_class, 'required_permissions', []),
            'cacheable': getattr(skill_class, 'cacheable', True),
            'cache_ttl': getattr(skill_class, 'cache_ttl', 3600),
            'version': getattr(skill_class, 'version', '1.0'),
            'author': getattr(skill_class, 'author', 'Unknown'),
            'tags': getattr(skill_class, 'tags', []),
            'category': getattr(skill_class, 'category', 'general'),
        }

    def _validate_skill_structure(self, skill_instance: Skill) -> None:
        """Valida la estructura básica de una skill sin requerir parámetros."""
        # Verificar que tiene parámetros definidos
        if not hasattr(skill_instance, 'parameters'):
            raise ValueError("Skill debe definir 'parameters'")

        if not isinstance(skill_instance.parameters, dict):
            raise ValueError("'parameters' debe ser un dict")

        # Verificar que cada parámetro tiene la estructura correcta
        for param_name, param_def in skill_instance.parameters.items():
            if not hasattr(param_def, 'name') or param_def.name != param_name:
                raise ValueError(f"Parámetro {param_name}: 'name' debe coincidir")

            if not hasattr(param_def, 'type') or not param_def.type:
                raise ValueError(f"Parámetro {param_name}: debe definir 'type'")

            if not hasattr(param_def, 'description') or not param_def.description:
                raise ValueError(f"Parámetro {param_name}: debe definir 'description'")

            if not hasattr(param_def, 'required'):
                raise ValueError(f"Parámetro {param_name}: debe definir 'required'")