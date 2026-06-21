"""
SkillRegistry — Registro central de skills.

Singleton que mantiene el catálogo de skills disponibles.
Responsabilidades:
- register(skill): registra una skill al arrancar la aplicación
- find_best_skill(intent, user_level): dada una intención, retorna la skill más adecuada
- get_by_name(name): obtiene una skill específica por su identificador
- list_available(user_level): lista todas las skills activas accesibles para ese nivel
- deactivate(name) / activate(name): control operacional sin reiniciar

F1-001: Integrado con SemanticSkillRouter como método primario de clasificación.
         El keyword matching queda como fallback graceful.

Refactor B — SPEC: plans/spec_tecnica_propifai_intelligence.md
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Type

from django.conf import settings

from .base import BaseSkill
from ..services.semantic_router import get_router, RoutingResult

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
    # F1-005: Aumentado de 0.25 a 0.45 para reducir falsos positivos
    MIN_CONFIDENCE_THRESHOLD = 0.45

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
        Dada una intención extraída por el LLM, retorna la skill más adecuada.

        Estrategia (F1-001):
        1. PRIMARIO: SemanticSkillRouter con embeddings E5-large
        2. FALLBACK: Keyword matching existente

        F1-005: Threshold aumentado de 0.25 a 0.45.

        Args:
            intent: Texto de intención del usuario
            user_level: Nivel de acceso del usuario
            active_context: Dict con contexto activo (opcional)

        Returns:
            Instancia de BaseSkill o None si no hay skill adecuada
        """
        if not intent or not intent.strip():
            return None

        # ── 1. PRIMARIO: Routing semántico ──
        router = get_router(threshold=self.MIN_CONFIDENCE_THRESHOLD)
        routing_result: RoutingResult = router.classify(intent)

        logger.info(
            f"[SkillRegistry] Routing — "
            f"semantic_skill={routing_result.skill_name}, "
            f"score={routing_result.score:.4f}, "
            f"threshold={routing_result.threshold}, "
            f"accepted={routing_result.accepted}, "
            f"latency={routing_result.latency_ms:.1f}ms"
        )

        if routing_result.accepted and routing_result.skill_name:
            skill = self._skills.get(routing_result.skill_name)
            if skill and skill.can_user_access(user_level):
                logger.debug(
                    f"[SkillRegistry] Skill por router semántico: "
                    f"'{skill.name}' (score: {routing_result.score:.4f})"
                )
                return skill

        # ── 2. FALLBACK: Keyword matching existente ──
        intent_lower = intent.lower().strip()

        _DISTRITOS_COMPUESTOS = [
            'cerro colorado', 'cerrocolorado',
            'jose luis bustamante', 'bustamante',
            'mariano melgar', 'selva alegre',
            'san juan de siguas', 'jacobo hunter',
            'la campiña', 'la campina', 'la joya',
        ]
        mensaje_menciona_distrito = any(
            d in intent_lower for d in _DISTRITOS_COMPUESTOS
        )

        intent_tokens = set(t for t in re.findall(r'\b\w{3,}\b', intent_lower))
        all_tokens_short = set(t for t in re.findall(r'\b\w+\b', intent_lower))

        if not intent_tokens and not mensaje_menciona_distrito:
            return None

        es_consulta_propiedades = bool(
            intent_tokens & _KEYWORDS_PROPIEDADES
        ) or mensaje_menciona_distrito

        es_seguimiento = False
        if active_context and not es_consulta_propiedades:
            _PALABRAS_SEGUIMIENTO = {
                'solo', 'tambien', 'y', 'en', 'de', 'con',
                'muestrame', 'dime', 'cuales', 'filtra', 'filtrar',
            }
            if (intent_tokens & _PALABRAS_SEGUIMIENTO) or (all_tokens_short & _PALABRAS_SEGUIMIENTO):
                es_seguimiento = True

        best_skill = None
        best_score = 0.0

        for name, skill in self._skills.items():
            if not skill.can_user_access(user_level):
                continue
            desc_lower = skill.description.lower()
            desc_tokens = set(t for t in re.findall(r'\b\w{3,}\b', desc_lower))
            if not desc_tokens:
                continue
            score = 0.0
            if es_seguimiento and name == 'busqueda_propiedades':
                score = 0.6
            elif es_consulta_propiedades and skill.category == 'busqueda':
                score = 0.3
                common = intent_tokens & desc_tokens
                if common:
                    score += len(common) / len(intent_tokens) * 0.5
                if name in intent_lower:
                    score += 0.2
            else:
                common = intent_tokens & desc_tokens
                if common:
                    score = len(common) / len(intent_tokens)
                    if name in intent_lower:
                        score += 0.2
                    if skill.category in intent_lower:
                        score += 0.1
            if score > best_score:
                best_score = score
                best_skill = skill

        if best_score >= self.MIN_CONFIDENCE_THRESHOLD:
            logger.debug(f"[Keyword] Skill: '{best_skill.name}' (score: {best_score:.2f})")
            return best_skill

        logger.debug(
            f"[SkillRegistry] Sin skill (keyword: {best_score:.2f}, "
            f"semantic: {routing_result.score:.4f})"
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
