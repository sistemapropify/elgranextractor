"""
SkillRegistry — Registro central de skills.

Singleton que mantiene el catálogo de skills disponibles.
Responsabilidades:
- register(skill): registra una skill al arrancar la aplicación
- find_best_skill(intent, user_level): dada una intención, retorna la skill más adecuada
- get_by_name(name): obtiene una skill específica por su identificador
- list_available(user_level): lista todas las skills activas accesibles para ese nivel
- deactivate(name) / activate(name): control operacional sin reiniciar

Refactor B — SPEC: plans/spec_tecnica_propifai_intelligence.md
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Type

from django.conf import settings

from .base import BaseSkill

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Palabras clave que indican intención de búsqueda de propiedades
# ═══════════════════════════════════════════════════════════════════════════════
# Refactor B1: Ampliado con términos faltantes que causaban falsos negativos
# (ej: 'construir', 'colegio', 'local', 'oficina', 'comercial')
# Refactor B2: Ahora es sobreescribible desde settings.PROPIEDADES_KEYWORDS
# ═══════════════════════════════════════════════════════════════════════════════

_KEYWORDS_PROPIEDADES_BASE = {
    # Tipos de propiedad (ampliado)
    'propiedad', 'propiedades', 'depa', 'depas', 'departamento', 'departamentos',
    'casa', 'casas', 'terreno', 'terrenos', 'lote', 'lotes',
    'inmueble', 'inmuebles', 'vivienda', 'viviendas',
    'local', 'locales', 'oficina', 'oficinas', 'consultorio', 'consultorios',
    'edificio', 'edificios', 'galpon', 'galpones', 'taller', 'talleres',
    'cochera', 'cocheras', 'estacionamiento', 'estacionamientos',
    'deposito', 'depositos', 'ambiente', 'ambientes',
    'penthouse', 'duplex', 'loft', 'flat',

    # Operaciones
    'alquiler', 'alquilo', 'alquila', 'alquilan', 'arriendo', 'arriendo',
    'vendo', 'vende', 'venden', 'venta', 'compro', 'compra', 'comprar',
    'remate', 'remates', 'subasta', 'subastas', 'permuta', 'permuto',

    # Consultas
    'disponible', 'disponibles', 'cuanto', 'cuantos', 'cuantas', 'cuanta',
    'precio', 'precios', 'costar', 'cuesta', 'cuestan', 'valor', 'valores',

    # Características
    'habitacion', 'habitaciones', 'cuarto', 'cuartos',
    'dormitorio', 'dormitorios', 'recamara', 'recamaras',
    'banio', 'banos', 'bano', 'banos', 'bano', 'bathroom',
    'area', 'metros', 'm2', 'metros2', 'metros_cuadrados',
    'piso', 'pisos', 'nivel', 'niveles', 'sotano', 'azotea',
    'amplio', 'amplios', 'amplia', 'amplias',
    'luminoso', 'luminosa', 'acogedor', 'acogedora',
    'amoblado', 'amoblada', 'semiamoblado',

    # Distritos de Arequipa (ampliado)
    'cayma', 'yanahuara', 'cercado', 'miraflores', 'sachaca',
    'cerro_colorado', 'cerrocolorado', 'mariano_melgar',
    'jose_luis_bustamante', 'bustamante', 'rivero',
    'paucarpata', 'socabaya', 'tiabaya', 'jacobo_hunter',
    'alto_selva_alegre', 'selva_alegre', 'characato',
    'sabandia', 'mollebaya', 'quebrada_honda',
    'san_juana_de_siguas', 'santa_rita', 'santa_isabel',
    'la_campina', 'la_joya', 'vitor', 'yura',

    # Verbos de acción (ampliado)
    'buscar', 'busca', 'busco', 'buscan', 'buscamos',
    'quiero', 'quiere', 'queremos', 'necesito', 'necesita',
    'mostrar', 'muestrame', 'muestrame', 'listar', 'lista',
    'ver', 'mirar', 'conocer', 'ensena', 'ensename',
    'recomendar', 'recomienda', 'sugerir', 'sugiere',
    'filtrar', 'filtra', 'ordenar', 'ordena',

    # Uso / propósito (NUEVOS — críticos para semántica)
    'construir', 'construccion', 'construiria', 'construyo',
    'colegio', 'colegios', 'educacion', 'escuela', 'escuelas',
    'universidad', 'universidades', 'instituto', 'institutos',
    'comercial', 'comercio', 'negocio', 'negocios',
    'industria', 'industrial', 'fabrica', 'fabricas',
    'vivienda', 'viviendas', 'residencial', 'habitacional',
    'proyecto', 'proyectos', 'inversion', 'invertir',
}

# Exponer como variable pública (puede sobreescribirse desde settings)
_KEYWORDS_PROPIEDADES = getattr(
    settings, 'PROPIEDADES_KEYWORDS', _KEYWORDS_PROPIEDADES_BASE
)


class SkillRegistry:
    """
    Registry central de skills. Implementación singleton.

    La selección de la mejor skill en find_best_skill() analiza la intención
    del usuario usando:
    1. Coincidencia de tokens con palabras clave del dominio
    2. Coincidencia de tokens con la descripción de cada skill
    3. Bonus por nombre de skill y categoría

    Si la confianza es menor al umbral configurado, retorna None (RAG puro).
    """

    _instance: Optional['SkillRegistry'] = None
    _skills: Dict[str, BaseSkill] = {}
    _skill_classes: Dict[str, Type[BaseSkill]] = {}

    # Umbral mínimo de confianza para selección semántica (0.0 - 1.0)
    MIN_CONFIDENCE_THRESHOLD = 0.25

    def __new__(cls) -> 'SkillRegistry':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._skills = {}
            cls._skill_classes = {}
        return cls._instance

    # ── Registro ─────────────────────────────────────────────────────────

    def register(self, skill_class: Type[BaseSkill]) -> None:
        """
        Registra una skill en el catálogo.

        Args:
            skill_class: Clase que hereda de BaseSkill

        Raises:
            ValueError: Si la clase no es válida
        """
        if not issubclass(skill_class, BaseSkill):
            raise ValueError(
                f"{skill_class.__name__} no hereda de BaseSkill"
            )

        # Validar que name no esté vacío
        if not skill_class.name:
            raise ValueError(
                f"Skill {skill_class.__name__} debe definir 'name'"
            )

        # Crear instancia
        try:
            skill_instance = skill_class()
        except Exception as e:
            raise ValueError(
                f"No se pudo instanciar skill '{skill_class.__name__}': {e}"
            )

        # Verificar que no exista ya (log warning pero reemplazar)
        if skill_class.name in self._skills:
            logger.warning(
                f"Skill '{skill_class.name}' ya registrada. Reemplazando..."
            )

        self._skills[skill_class.name] = skill_instance
        self._skill_classes[skill_class.name] = skill_class
        logger.info(
            f"Skill registrada: '{skill_class.name}' "
            f"(categoría: {skill_class.category}, nivel: {skill_class.access_level})"
        )

    # ── Búsqueda ──────────────────────────────────────────────────────────

    def find_best_skill(
        self,
        intent: str,
        user_level: int = 1,
        active_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[BaseSkill]:
        """
        Dada una intención extraída por el LLM, retorna la skill más adecuada
        que el usuario tiene permiso de usar.

        Estrategia de matching:
        1. Detectar si la intención contiene palabras clave del dominio (propiedades)
        2. Si sí, calcular score contra skills de búsqueda
        3. Si no, buscar en todas las skills por coincidencia de tokens
        4. Si hay contexto activo, considerar mensajes de seguimiento (B4)

        Refactor B3: Nuevo parámetro active_context para mejorar routing
        cuando hay contexto conversacional activo.
        Refactor B4: Detección de mensajes de seguimiento — si hay contexto
        activo y el mensaje no tiene keywords propias, asumir que es
        continuación de la búsqueda anterior.

        Args:
            intent: Texto de intención del usuario (ej: 'buscar depas en Cayma')
            user_level: Nivel de acceso del usuario
            active_context: Dict con contexto activo (opcional)

        Returns:
            Instancia de BaseSkill o None si no hay skill adecuada
        """
        if not intent or not intent.strip():
            return None

        intent_lower = intent.lower().strip()

        # Extraer tokens relevantes (>= 3 caracteres)
        intent_tokens = set(
            t for t in re.findall(r'\b\w{3,}\b', intent_lower)
        )

        if not intent_tokens:
            return None

        # Detectar si la intención es sobre propiedades
        es_consulta_propiedades = bool(
            intent_tokens & _KEYWORDS_PROPIEDADES
        )

        # ── B4: Detección de mensajes de seguimiento ──────────────────────
        # Si hay contexto activo pero el mensaje NO contiene keywords de
        # propiedades, puede ser un mensaje de seguimiento (ej: "solo
        # departamentos", "y en cayma", "muestrame").
        # En ese caso, forzamos busqueda_propiedades.
        es_seguimiento = False
        if (
            active_context
            and not es_consulta_propiedades
        ):
            # Palabras que indican seguimiento/refinamiento
            _PALABRAS_SEGUIMIENTO = {
                'solo', 'solamente', 'unicamente', 'tambien',
                'y', 'pero', 'entonces', 'ahora',
                'muestrame', 'listame', 'dime', 'ensename',
                'cuales', 'cuales', 'cuantas', 'cuantos',
                'refinar', 'filtra', 'filtrar',
            }
            if intent_tokens & _PALABRAS_SEGUIMIENTO:
                es_seguimiento = True
                logger.debug(
                    f"[find_best_skill] Mensaje de seguimiento detectado: "
                    f"'{intent}' (contexto activo presente)"
                )

        best_skill = None
        best_score = 0.0

        for name, skill in self._skills.items():
            # Verificar acceso del usuario
            if not skill.can_user_access(user_level):
                continue

            desc_lower = skill.description.lower()
            desc_tokens = set(
                t for t in re.findall(r'\b\w{3,}\b', desc_lower)
            )

            if not desc_tokens:
                continue

            score = 0.0

            # ── B4: Si es seguimiento, dar bonus fuerte a busqueda_propiedades ──
            if es_seguimiento and name == 'busqueda_propiedades':
                score = 0.6  # Score alto directo para seguimiento
            # Si es consulta de propiedades y la skill es de búsqueda
            elif es_consulta_propiedades and skill.category == 'busqueda':
                # Score base por ser la skill correcta para el dominio
                score = 0.3

                # Coincidencia de tokens con la descripción
                common = intent_tokens & desc_tokens
                if common:
                    # Proporción de tokens de la intención que están en la descripción
                    score += len(common) / len(intent_tokens) * 0.5

                # Bonus si el nombre de la skill está en la intención
                if name in intent_lower:
                    score += 0.2

            else:
                # Para otras skills, matching general de tokens
                common = intent_tokens & desc_tokens
                if common:
                    score = len(common) / len(intent_tokens)

                    # Bonus por nombre
                    if name in intent_lower:
                        score += 0.2

                    # Bonus por categoría
                    if skill.category in intent_lower:
                        score += 0.1

            if score > best_score:
                best_score = score
                best_skill = skill

        # Solo retornar si supera el umbral
        if best_score >= self.MIN_CONFIDENCE_THRESHOLD:
            logger.debug(
                f"Skill seleccionada: '{best_skill.name}' "
                f"(score: {best_score:.2f}, umbral: {self.MIN_CONFIDENCE_THRESHOLD})"
            )
            return best_skill

        logger.debug(
            f"Ninguna skill superó el umbral de confianza "
            f"(mejor score: {best_score:.2f}, umbral: {self.MIN_CONFIDENCE_THRESHOLD})"
        )
        return None

    def get_by_name(self, name: str) -> Optional[BaseSkill]:
        """
        Obtiene una skill por su identificador único.

        Args:
            name: Nombre de la skill (snake_case)

        Returns:
            Instancia de BaseSkill o None si no existe
        """
        return self._skills.get(name)

    # ── Listado ───────────────────────────────────────────────────────────

    def list_available(self, user_level: int = 1) -> List[Dict[str, Any]]:
        """
        Lista todas las skills activas accesibles para un nivel de usuario.

        Args:
            user_level: Nivel de acceso del usuario

        Returns:
            Lista de schemas de skills disponibles
        """
        return [
            skill.get_schema()
            for skill in self._skills.values()
            if skill.can_user_access(user_level)
        ]

    def list_all(self) -> List[Dict[str, Any]]:
        """Lista todas las skills registradas (activas e inactivas)."""
        return [
            skill.get_schema()
            for skill in self._skills.values()
        ]

    # ── Compatibilidad hacia atrás ─────────────────────────────────────────

    def list_skills(self) -> Dict[str, Dict[str, Any]]:
        """
        Alias de compatibilidad para el viejo SkillRegistry.
        Retorna dict {skill_name: schema_dict} para mantener compatibilidad
        con orchestrator.py y vistas que usan la API antigua.
        """
        return {
            schema['name']: schema
            for schema in self.list_all()
        }

    def discover_skills(self, *args, **kwargs) -> None:
        """
        No-op de compatibilidad. El nuevo SkillRegistry requiere registro
        explícito via register() en lugar de auto-descubrimiento.
        """
        logger.debug(
            "discover_skills() llamado pero es no-op en el nuevo SkillRegistry. "
            "Usar register() explícitamente."
        )

    def search_skills(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Busca skills por coincidencia en nombre/descripción.
        Compatibilidad con el sistema de skills anterior.

        Args:
            query: Texto de búsqueda
            limit: Máximo de resultados a retornar

        Returns:
            Lista de schemas de skills que coinciden
        """
        query_lower = query.lower().strip()
        results = []
        for skill in self._skills.values():
            if query_lower in skill.name.lower() or query_lower in skill.description.lower():
                results.append(skill.get_schema())
        return results[:limit]

    # ── Control operacional ───────────────────────────────────────────────

    def deactivate(self, name: str) -> bool:
        """
        Desactiva una skill sin eliminarla del registro.

        Args:
            name: Nombre de la skill

        Returns:
            True si se desactivó, False si no existe
        """
        skill = self._skills.get(name)
        if skill:
            skill.is_active = False
            logger.info(f"Skill desactivada: '{name}'")
            return True
        return False

    def activate(self, name: str) -> bool:
        """
        Reactiva una skill desactivada.

        Args:
            name: Nombre de la skill

        Returns:
            True si se activó, False si no existe
        """
        skill = self._skills.get(name)
        if skill:
            skill.is_active = True
            logger.info(f"Skill activada: '{name}'")
            return True
        return False

    # ── Estadísticas ──────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del registry."""
        total = len(self._skills)
        activas = sum(1 for s in self._skills.values() if s.is_active)
        por_categoria: Dict[str, int] = {}
        for s in self._skills.values():
            por_categoria[s.category] = por_categoria.get(s.category, 0) + 1

        return {
            'total': total,
            'activas': activas,
            'inactivas': total - activas,
            'por_categoria': por_categoria,
            'skills': list(self._skills.keys()),
        }

    def clear(self) -> None:
        """Limpia todas las skills registradas (útil para tests)."""
        self._skills.clear()
        self._skill_classes.clear()
        logger.info("SkillRegistry limpiado")
