# ADDENDUM: Ajustes a Requisitos y Precondiciones según código real de `formatear_propiedades`

> Corrige dos specs previos (`SPEC_requisitos_completos_react_loop.md` y `SPEC_precondiciones_skills.md`) a la luz del código real de `FormatearPropiedadesSkill`. No reemplaza esos specs — los corrige en los puntos donde asumieron un contrato de skill distinto al real.

---

## 1. Por qué hace falta este ajuste

El código real revela dos comportamientos que mis checks anteriores no contemplaban:

```python
# validate_params() — 'propiedades' NO es obligatorio
if 'formato' not in params or params.get('formato') not in ('carrusel', 'matriz', 'lista'):
    return False
return True   # ← no valida 'propiedades'

# execute() — fallback a memoria conversacional
if not propiedades and context and hasattr(context, 'metadata'):
    ultima = context.metadata.get('ultima_busqueda', {})
    if ultima and ultima.get('resultados'):
        propiedades = ultima['resultados']

# resultado vacío = SkillResult.ok(), no error
if not propiedades:
    return SkillResult.ok(data={'html': '<p>No hay propiedades para mostrar.</p>', 'total': 0}, ...)
```

Consecuencia para mis specs anteriores:
- La precondición de Capa 1 (`_busqueda_exacta_precondition`-style check aplicado también a `formatear_propiedades`) es más estricta de lo necesario — bloquearía follow-ups legítimos que la skill ya sabe resolver vía `ultima_busqueda`.
- El chequeo de satisfacción de requisitos (`has_valid_result = bool(step.skill_result)`) marcaría como cumplido un requisito de formato aunque el carrusel esté vacío, porque el diccionario de retorno es truthy incluso con `total: 0`.

---

## 2. Fix 1 — Precondición de `formatear_propiedades` debe mirar también el contexto

**Reemplaza** la entrada de `formatear_propiedades` en `SKILL_PRECONDITIONS` (spec de precondiciones, sección 2.1):

```python
def _formatear_propiedades_precondition(steps_history: list["AgentStep"], context: dict) -> bool:
    """formatear_propiedades puede recibir propiedades de un paso previo EN ESTE RUN,
    o recuperarlas de la memoria conversacional (ultima_busqueda) — igual que hace
    la skill internamente. La precondición debe reflejar ambas fuentes, no solo el run actual."""
    tiene_paso_previo_con_datos = any(
        step.skill_result and _result_item_count(step.skill_result) > 0
        for step in steps_history
    )
    tiene_contexto_conversacional = bool(
        context.get('metadata', {}).get('ultima_busqueda', {}).get('resultados')
    )
    return tiene_paso_previo_con_datos or tiene_contexto_conversacional


SKILL_PRECONDITIONS: dict[str, SkillPrecondition] = {
    'busqueda_exacta': _busqueda_exacta_precondition,
    'formatear_propiedades': _formatear_propiedades_precondition,   # ← reemplaza la versión anterior
}
```

Con esto, en una conversación de seguimiento ("de esos que me mostraste, dame el carrusel") donde no hay un paso previo *en este run* pero sí hay `ultima_busqueda` en memoria, `formatear_propiedades` sigue disponible como opción — antes de este ajuste, la Capa 1 la habría bloqueado incorrectamente.

---

## 3. Fix 2 — Satisfacción de requisitos basada en `total`, no en truthy del dict

**Reemplaza** la función auxiliar del spec de requisitos completos:

```python
def _result_item_count(skill_result: Optional[dict]) -> int:
    """Extrae la cantidad real de items de un resultado de skill.
    Todas las skills del catálogo devuelven 'total' de forma consistente
    (busqueda_propiedades, busqueda_exacta, formatear_propiedades, etc.) —
    se usa ese campo en vez de inspeccionar listas anidadas o solo chequear
    si el dict es truthy (un dict con total=0 sigue siendo truthy)."""
    if not isinstance(skill_result, dict):
        return 0
    if 'total' in skill_result:
        return skill_result.get('total') or 0
    # fallback defensivo si alguna skill futura no reporta 'total'
    for value in skill_result.values():
        if isinstance(value, list):
            return len(value)
    return 0
```

**Reemplaza** `_update_requirements_status()` (del spec de estado monotónico) para usar esta función en vez de `bool(step.skill_result)`:

```python
def _update_requirements_status(self, requirements: list[Requirement], step: AgentStep) -> None:
    if step.status == AgentStatus.FAILED or not step.skill_used:
        return

    skill_kind = SKILL_SATISFIES_KIND.get(step.skill_used)
    if skill_kind is None:
        return

    item_count = _result_item_count(step.skill_result)
    if item_count == 0:
        return   # CAMBIO CLAVE: un resultado con total=0 no satisface nada,
                 # aunque el SkillResult.success sea True

    for requirement in requirements:
        if requirement.satisfied:
            continue
        if requirement.kind == skill_kind:
            requirement.satisfied = True
            requirement.satisfied_by_skill = step.skill_used
```

---

## 4. Caso nuevo a contemplar: cero resultados es un estado final válido, no un error

Con el fix de la sección 3, si `busqueda_propiedades` genuinamente no encuentra nada (`total: 0`), el requisito `data` nunca se marca satisfecho — y el loop seguirá intentando (correcto, no debe declarar éxito). Pero hay que evitar que esto genere un loop infinito de reintentos inútiles cuando la respuesta correcta es simplemente "no hay terrenos en esa zona":

```python
def _observe(self, original_message, step, requirements, steps_history, context) -> dict:
    self._update_requirements_status(requirements, step)

    # Detectar "cero resultados genuino" — no es un fallo, es una respuesta válida
    if step.skill_used in DATA_SKILLS and _result_item_count(step.skill_result) == 0:
        intentos_de_busqueda = sum(1 for s in steps_history if s.skill_used in DATA_SKILLS)
        if intentos_de_busqueda >= 2:
            # ya probó buscar de más de una forma y sigue sin resultados —
            # es momento de responder "no hay" en vez de seguir intentando
            return {
                'is_sufficient': True,
                'reason': 'búsqueda sin resultados confirmada tras reintento',
                'final_answer_override': {'total': 0, 'mensaje': 'No se encontraron propiedades que coincidan.'},
            }

    pending = [r for r in requirements if not r.satisfied]
    if not pending:
        return {'is_sufficient': True, 'reason': 'todos los requisitos cumplidos'}
    return {'is_sufficient': False, 'pending_requirements': [r.description for r in pending]}
```

`DATA_SKILLS = {'busqueda_propiedades', 'busqueda_exacta', 'matching_hibrido', 'acm_analisis'}` — mismo conjunto que ya usas en `SKILL_SATISFIES_KIND` para `kind='data'`.

Con esto: si de verdad no hay terrenos en Cerro Colorado, el agente busca de una forma, y si falla, prueba otra (ej. `busqueda_propiedades` con filtro más amplio) — y recién al segundo intento sin resultados, concluye y responde honestamente, en vez de agotar `max_iterations` sin necesidad ni fingir que encontró algo.

---

## 5. Detalle adicional aprovechable: el campo `total` también sirve para el checklist de formato

Como `formatear_propiedades` también devuelve `total` (reflejando cuántas propiedades formateó), el mismo `_result_item_count()` sirve para ambos tipos de requisito sin lógica separada — ya lo contempla el fix de la sección 3 porque no distingue por skill, solo por el campo `total` del resultado. No hace falta tratamiento especial para el requisito `format`.

---

## 6. Test unitario adicional (extiende el de `SPEC_estado_monotonico_requisitos.md`)

```python
def test_resultado_vacio_no_satisface_requisito():
    requirements = [Requirement(id="req_1", description="buscar terrenos", kind="data")]

    step_busqueda_vacia = AgentStep(
        iteration=0, thought="...", skill_used="busqueda_propiedades",
        skill_params={}, skill_result={"propiedades": [], "total": 0},
        status=AgentStatus.OBSERVING,
    )
    _update_requirements_status(requirements, step_busqueda_vacia)

    assert requirements[0].satisfied is False   # total=0 NO debe marcar como cumplido


def test_formatear_con_fallback_contexto_no_bloqueado_por_precondicion():
    steps_history = []  # sin pasos previos en este run
    context = {'metadata': {'ultima_busqueda': {'resultados': [{'id': 1}]}}}

    disponible = _formatear_propiedades_precondition(steps_history, context)
    assert disponible is True   # debe permitirse por el fallback conversacional
```

---

## 7. Criterios de aceptación (adicionales a los ya definidos en los specs previos)

- [ ] `_result_item_count()` reemplaza cualquier chequeo de `bool(skill_result)` en `_update_requirements_status()` y en las funciones de precondición.
- [ ] Un resultado con `total: 0` nunca marca un requisito como satisfecho, aunque `SkillResult.success` sea `True`.
- [ ] `formatear_propiedades` sigue disponible como opción cuando hay `ultima_busqueda` en contexto, incluso sin pasos previos en el run actual.
- [ ] Tras dos intentos de búsqueda sin resultados, el agente concluye con una respuesta honesta de "no se encontraron resultados" en vez de agotar `max_iterations`.
- [ ] Los dos tests unitarios de la sección 6 pasan.
