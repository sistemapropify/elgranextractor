"""
Precondiciones de Skills y Exclusión por Fallos Repetidos.

SPEC: precondiciones_skills.md

Dos capas de protección:
  Capa 1 (preventiva): filtra skills que no pueden ejecutarse en el estado actual.
  Capa 2 (defensiva): excluye skills que fallaron N veces seguidas.

Uso:
  from .skill_preconditions import get_available_skills, resolve_skill_substitution
  
  # En _think():
  available = get_available_skills(allowed_skills, steps_history, context)
  
  # Antes de ejecutar:
  skill_name = resolve_skill_substitution(skill_name, steps_history)
"""

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .base_agent import AgentStep, Requirement

# Tipo de precondición: recibe historial de pasos y contexto, retorna bool
SkillPrecondition = Callable[[List["AgentStep"], Dict[str, Any]], bool]


# ── Helper: extraer propiedades de un skill_result ─────────────────────────


def _extract_properties(skill_result: Optional[dict]) -> Optional[list]:
    """Extrae lista de propiedades de un skill_result, en cualquier formato."""
    if not skill_result:
        return None
    if isinstance(skill_result, list):
        return skill_result
    if isinstance(skill_result, dict):
        for key in ('resultados', 'properties', 'propiedades', 'data'):
            val = skill_result.get(key)
            if isinstance(val, list) and len(val) > 0:
                return val
    return None


# ── Capa 1: Precondiciones de skills ──────────────────────────────────────


def _busqueda_exacta_precondition(steps_history: List["AgentStep"],
                                   context: Dict[str, Any]) -> bool:
    """busqueda_exacta requiere una lista de propiedades de un paso anterior."""
    return any(
        step.skill_result and _extract_properties(step.skill_result)
        for step in steps_history
    )


def _formatear_propiedades_precondition(steps_history: List["AgentStep"],
                                         context: Dict[str, Any]) -> bool:
    """formatear_propiedades puede recibir propiedades de un paso previo EN ESTE RUN,
    o recuperarlas de la memoria conversacional (ultima_busqueda).

    ADDENDUM: formatear_propiedades_real — Sección 2
    La skill internamente ya busca en context.metadata.ultima_busqueda si no recibe
    propiedades como parámetro. La precondición debe reflejar ambas fuentes.
    """
    # Fuente 1: paso previo en este mismo run
    tiene_paso_previo = any(
        step.skill_result and _extract_properties(step.skill_result)
        for step in steps_history
    )
    if tiene_paso_previo:
        return True

    # Fuente 2: contexto conversacional (ultima_busqueda de conversación anterior)
    if isinstance(context, dict):
        metadata = context.get('metadata', {})
        if isinstance(metadata, dict):
            ultima = metadata.get('ultima_busqueda', {})
            if isinstance(ultima, dict) and ultima.get('resultados'):
                return True

    return False


# Skills sin entrada en este dict se consideran siempre disponibles
# (busqueda_propiedades, acm_analisis, etc. no dependen de un paso previo)
SKILL_PRECONDITIONS: Dict[str, SkillPrecondition] = {
    'busqueda_exacta': _busqueda_exacta_precondition,
    'formatear_propiedades': _formatear_propiedades_precondition,
}


# ── Capa 2: Exclusión por fallos repetidos ────────────────────────────────

MAX_CONSECUTIVE_FAILURES = 2


def track_consecutive_failures(steps_history: List["AgentStep"]) -> Dict[str, int]:
    """
    Cuenta fallos consecutivos por skill, desde el final hacia atrás.
    
    SPEC: precondiciones_skills.md — Sección 2, Capa 2.
    Se corta el conteo al encontrar un éxito más reciente para esa skill.
    """
    from .base_agent import AgentStatus
    counts: Dict[str, int] = {}
    for step in reversed(steps_history):
        if step.skill_used is None:
            continue
        if step.status == AgentStatus.FAILED:
            counts[step.skill_used] = counts.get(step.skill_used, 0) + 1
        else:
            # Si la skill tuvo éxito, reiniciar su contador
            counts[step.skill_used] = 0
    return counts


# ── Función principal: skills disponibles ahora ───────────────────────────


def get_available_skills(
    allowed_skills: List[str],
    steps_history: List["AgentStep"],
    context: Dict[str, Any],
    requirements: Optional[List["Requirement"]] = None,
) -> List[str]:
    """
    Filtra allowed_skills a solo las que son ejecutables ahora mismo.
    
    SPEC: precondiciones_skills.md — Sección 2.
    SPEC: skill_contamination_taxonomia.md — Sección 3.4 (relevance filter)
    
    1. Filtra por precondiciones (skills que requieren pasos previos).
    2. Excluye skills con MAX_CONSECUTIVE_FAILURES fallos seguidos.
    3. Filtra por relevancia: solo skills cuyo 'kind' corresponde a un requisito
       TODAVÍA PENDIENTE. Si no hay requisitos pendientes, no hay skills que ofrecer.
    
    Returns:
        Lista de nombres de skills disponibles en este momento.
    """
    from .base_agent import AgentStatus, SKILL_SATISFIES_KIND

    # Paso 1: Filtrar por precondiciones
    precondition_filtered = [
        s for s in allowed_skills
        if s not in SKILL_PRECONDITIONS or SKILL_PRECONDITIONS[s](steps_history, context)
    ]

    # Paso 2: Excluir por fallos repetidos
    failure_counts = track_consecutive_failures(steps_history)
    result = [
        s for s in precondition_filtered
        if failure_counts.get(s, 0) < MAX_CONSECUTIVE_FAILURES
    ]

    # Paso 3 (NUEVO): relevancia — solo ofrecer skills cuyo kind
    # corresponde a un requisito TODAVÍA PENDIENTE.
    # Esto evita que el LLM elija skills de matching o comparación
    # cuando no hay requisitos de ese tipo (SPEC_skill_contamination_taxonomia.md — Sección 3.4)
    if requirements is not None:
        kinds_pendientes = {r.kind for r in requirements if not r.satisfied}
        result = [
            s for s in result
            if s not in SKILL_SATISFIES_KIND or SKILL_SATISFIES_KIND[s] in kinds_pendientes
        ]

    return result


# ── Sustitución determinista ──────────────────────────────────────────────


def resolve_skill_substitution(
    skill_name: str,
    steps_history: List["AgentStep"],
) -> str:
    """
    Sustitución determinista para casos conocidos donde la skill elegida
    no puede ejecutarse sin un paso previo que no existe.
    
    SPEC: precondiciones_skills.md — Sección 3.
    
    Esto es un refuerzo adicional a Capa 1: si el LLM ignora la lista
    de skills disponibles y elige una no disponible, se sustituye aquí.
    """
    if skill_name == 'busqueda_exacta' and not _busqueda_exacta_precondition(steps_history, {}):
        return 'busqueda_propiedades'
    if skill_name == 'formatear_propiedades' and not _formatear_propiedades_precondition(steps_history, {}):
        return 'busqueda_propiedades'
    return skill_name
