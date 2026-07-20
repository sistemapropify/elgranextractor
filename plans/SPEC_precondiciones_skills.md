# SPEC: Precondiciones de Skills y Exclusión por Fallos Repetidos — Propifai (PIL)

> **Objetivo:** evitar que el agente reintente una skill que no puede tener éxito en el estado actual del loop (ej. `busqueda_exacta` sin `propiedades` previas), y garantizar que ninguna skill se reintente indefinidamente sin cambiar de estrategia.
> **Caso reproducido:** consulta "terrenos en Cerro Colorado en carrusel" → agente elige `busqueda_exacta` en iteración 0 (sin datos previos que filtrar) → falla → LLM la vuelve a elegir en iteraciones 1-4 → `max_iterations` alcanzado → AgentGraph falla → cae a LangGraph fallback, que sí resuelve la consulta con `SearchAgent` directo.
> **Principio de diseño:** las dependencias entre skills son información determinista que ya existe en tu código (documentaste tú mismo que `busqueda_exacta` necesita `propiedades` de un paso anterior). No debe delegarse en el LLM decidir esto en cada iteración — se calcula en código y se le presenta al LLM solo el conjunto de opciones válidas.

---

## 1. Diagnóstico de causa raíz

### 1.1 Por qué el LLM insiste en la misma skill inválida

`_think()` recibe la lista completa de `allowed_skills` del agente sin filtrar por si son ejecutables en este momento del loop. `busqueda_exacta` aparece como opción disponible en la iteración 0 tanto como en la iteración 4 — nada en el prompt le indica al LLM que esa opción es estructuralmente inválida sin un paso previo. El LLM ve "fallé" pero no necesariamente entiende *por qué* de forma que lo lleve a descartar la opción — puede interpretar el fallo como algo corregible con otros parámetros, y seguir intentando variaciones de la misma skill equivocada.

### 1.2 Por qué esto no se arregla "mejorando el prompt"

Aunque se le explique mejor al LLM en el `system_prompt` que "`busqueda_exacta` requiere resultados previos", seguís dependiendo de que el LLM interprete correctamente esa regla en cada llamada — es una apuesta probabilística sobre algo que es 100% determinista. La dependencia entre skills (`busqueda_exacta` necesita `propiedades`) es un hecho conocido de tu código, no una decisión de negocio que el LLM deba razonar. Debe aplicarse como filtro antes de que el LLM elija, no como sugerencia dentro del prompt.

---

## 2. Diseño: dos capas de protección

### Capa 1 (preventiva): precondiciones de skill — filtra opciones inválidas antes de ofrecerlas

**Ubicación:** `agents/skill_preconditions.py` (nuevo)

```python
from typing import Callable

SkillPrecondition = Callable[[list["AgentStep"], dict], bool]


def _busqueda_exacta_precondition(steps_history: list["AgentStep"], context: dict) -> bool:
    """busqueda_exacta requiere una lista de propiedades de un paso anterior."""
    return any(
        step.skill_result and _extract_properties(step.skill_result)
        for step in steps_history
    )


SKILL_PRECONDITIONS: dict[str, SkillPrecondition] = {
    'busqueda_exacta': _busqueda_exacta_precondition,
    'formatear_propiedades': lambda steps, ctx: any(
        s.skill_result and _extract_properties(s.skill_result) for s in steps
    ),
    # skills sin entrada en este dict se consideran siempre disponibles
    # (busqueda_propiedades, acm_analisis, etc. no dependen de un paso previo)
}


def get_available_skills(allowed_skills: list[str], steps_history: list["AgentStep"],
                          context: dict) -> list[str]:
    """Filtra allowed_skills a solo las que son ejecutables ahora mismo."""
    return [
        s for s in allowed_skills
        if s not in SKILL_PRECONDITIONS or SKILL_PRECONDITIONS[s](steps_history, context)
    ]
```

**Uso en `_think()`:**

```python
def _think(self, original_message, requirements, steps_history, context) -> dict:
    available_now = get_available_skills(self.definition.allowed_skills, steps_history, context)
    excluded = set(self.definition.allowed_skills) - set(available_now)

    prompt = self.definition.system_prompt + f"""
    ...
    SKILLS DISPONIBLES AHORA (solo estas son válidas en este momento):
    {', '.join(available_now)}

    {"SKILLS NO DISPONIBLES TODAVÍA: " + ', '.join(excluded) + " (requieren un paso previo que aún no existe)" if excluded else ""}
    ...
    """
```

Con esto, en la iteración 0 de tu caso, `busqueda_exacta` **ni siquiera aparece como opción** — el LLM literalmente no puede elegirla porque no está en la lista. Esto resuelve el caso específico de raíz, sin depender de que razone bien.

### Capa 2 (defensiva): exclusión por fallos repetidos — red de seguridad general

Aunque la Capa 1 cubre el caso conocido, cualquier otra skill puede fallar por razones no modeladas como precondición (ej. un error transitorio de red, un parámetro mal extraído). Para que el loop nunca se quede atascado repitiendo lo mismo, sin importar la causa:

```python
@dataclass
class AgentStep:
    # ...campos existentes...
    error_message: Optional[str] = None   # nuevo campo


def track_consecutive_failures(steps_history: list[AgentStep]) -> dict[str, int]:
    """Cuenta fallos consecutivos por skill, mirando desde el final hacia atrás."""
    counts: dict[str, int] = {}
    for step in reversed(steps_history):
        if step.skill_used is None:
            continue
        if step.status == AgentStatus.FAILED:
            counts[step.skill_used] = counts.get(step.skill_used, 0) + 1
        else:
            break  # se corta el conteo apenas aparece un éxito más reciente
    return counts


MAX_CONSECUTIVE_FAILURES = 2

def get_available_skills(allowed_skills, steps_history, context) -> list[str]:
    precondition_filtered = [
        s for s in allowed_skills
        if s not in SKILL_PRECONDITIONS or SKILL_PRECONDITIONS[s](steps_history, context)
    ]
    failure_counts = track_consecutive_failures(steps_history)
    return [
        s for s in precondition_filtered
        if failure_counts.get(s, 0) < MAX_CONSECUTIVE_FAILURES
    ]
```

Si `busqueda_exacta` (o cualquier skill) falla 2 veces seguidas, se excluye de las opciones para el resto del loop — el LLM se ve forzado a intentar algo distinto, sin importar si la causa del fallo estaba modelada como precondición o no.

### 2.1 Mensaje de fallo explícito hacia el LLM

Cuando una skill falla, el motivo debe ser legible en la siguiente llamada a `_think()`, no solo un booleano:

```python
# en el loop principal, tras ejecutar la skill
if not skill_result.success:
    step.status = AgentStatus.FAILED
    step.error_message = skill_result.message or "fallo sin detalle"
```

```python
def _summarize_steps(self, steps_history: list[AgentStep]) -> str:
    lines = []
    for s in steps_history:
        if s.status == AgentStatus.FAILED:
            lines.append(f"- Intentaste '{s.skill_used}' y FALLÓ: {s.error_message}. No la repitas.")
        elif s.skill_used:
            lines.append(f"- Ejecutaste '{s.skill_used}' con éxito.")
    return "\n".join(lines)
```

Esto se inyecta en el prompt de `_think()` junto al checklist de requisitos ya implementado — el LLM ve explícitamente "fallaste con X, no la repitas" en vez de tener que inferirlo de un resultado vacío.

---

## 3. Guardrail de piso: nunca fallar sin intentar la alternativa obvia

Como refuerzo adicional específico a este caso (no genérico, pero de bajo costo y alto valor): si `busqueda_exacta` es la única skill considerada y no hay `propiedades` previas, sustituir automáticamente por `busqueda_propiedades` en código, sin pasar por el LLM — es una regla de negocio 100% determinista, no una decisión que valga la pena delegar.

```python
def _resolve_skill_substitution(skill_name: str, steps_history: list[AgentStep]) -> str:
    """Sustitución determinista para casos conocidos donde la skill elegida
    no puede ejecutarse sin un paso previo que no existe."""
    if skill_name == 'busqueda_exacta' and not _busqueda_exacta_precondition(steps_history, {}):
        return 'busqueda_propiedades'
    return skill_name
```

Esto es opcional frente a la Capa 1 (que ya evita que el LLM elija `busqueda_exacta` sin precondición) — pero sirve como tercera red de seguridad si, por ejemplo, el LLM ignora la lista de "disponibles ahora" del prompt (los LLMs no siempre respetan restricciones textuales al 100%). Aplícalo justo antes de ejecutar la skill, como último filtro.

---

## 4. Por qué esto no debería haber pasado ya con el fix de requisitos completos

Vale aclarar: el sistema de requisitos (spec anterior) funcionó exactamente como se diseñó — detectó correctamente que faltaba el requisito de formato. El problema de hoy es independiente y anterior en la cadena: el agente nunca llegó a tener datos que formatear porque se quedó atascado en el primer paso. Son dos capas de protección distintas y complementarias: una asegura que no se declare "listo" sin cumplir todo (ya funciona); esta asegura que no se quede girando en el mismo error sin avanzar (falta implementar). Ambas son necesarias.

---

## 5. Observabilidad — extender `reasoning_steps`

```json
{
    "icon": "🚫",
    "title": "Skill excluida temporalmente",
    "description": "busqueda_exacta no disponible: requiere resultados de un paso previo",
    "type": "skill_precondition_blocked",
    "order": 1
},
{
    "icon": "⚠️",
    "title": "Skill excluida por fallos repetidos",
    "description": "busqueda_exacta falló 2 veces consecutivas, excluida del resto del loop",
    "type": "skill_failure_exclusion",
    "order": 2
}
```

Esto también enriquece el job de recalibración nocturna: si una skill aparece repetidamente en `skill_precondition_blocked`, es señal de que su definición de precondición está mal calibrada o de que el prompt del agente debería mencionarla explícitamente desde el inicio.

---

## 6. Suite de regresión — casos obligatorios

```python
CASOS_REGRESION_PRECONDICIONES = [
    {
        "query": "terrenos en cerro colorado en carrusel",
        "skill_no_esperada_en_iteracion_0": "busqueda_exacta",
        "skills_esperadas_en_orden": ["busqueda_propiedades", "formatear_propiedades"],
    },
    {
        # caso donde SÍ debe poder usar busqueda_exacta: ya hay propiedades previas
        "query": "de esos terrenos, dame solo los que tengan más de 300 metros",
        "contexto_previo": {"propiedades_encontradas": ["..."]},  # simula resultado previo
        "skills_esperadas_en_orden": ["busqueda_exacta"],
    },
]
```

El segundo caso es importante: confirma que el filtro de precondiciones no bloquea `busqueda_exacta` cuando sí hay datos previos válidos — la Capa 1 debe ser un filtro contextual, no una prohibición permanente de la skill.

---

## 7. Criterios de aceptación

- [ ] La consulta "terrenos en Cerro Colorado en carrusel" nunca ofrece `busqueda_exacta` como opción en la iteración 0 (verificable inspeccionando el prompt enviado a `_think()`).
- [ ] Ninguna skill se ejecuta más de `MAX_CONSECUTIVE_FAILURES` (2) veces seguidas dentro del mismo loop, sin importar la causa del fallo.
- [ ] El caso de regresión con contexto previo confirma que `busqueda_exacta` sigue disponible cuando sí hay `propiedades` que filtrar.
- [ ] El AgentGraph resuelve el caso reproducido sin caer al fallback de LangGraph.
- [ ] `reasoning_steps` refleja las exclusiones (por precondición o por fallos) de forma visible en el dashboard.
- [ ] `AgentStep.error_message` queda poblado en cada fallo, no solo un booleano de éxito/fracaso.

---

## 8. Nota sobre el fallback que "salvó" la respuesta

Vale la pena resaltar algo positivo de tu propio log: el sistema se comportó exactamente como está diseñado en el spec de refactor original — cuando el `AgentGraph` (primario) falla, `LangGraph` (fallback 1) tomó el control y sí resolvió la consulta. Eso significa que tu red de seguridad de fallbacks en cascada ya está funcionando en producción, cubriéndote mientras corriges el problema de fondo. No es una señal de que "el sistema nuevo es peor" — es la señal de que el diseño de fallbacks que especificaste está haciendo exactamente su trabajo.
