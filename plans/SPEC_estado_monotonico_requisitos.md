# SPEC: Estado Monotónico en el Tracking de Requisitos — Propifai (PIL)

> **Objetivo:** corregir que `_update_requirements_status()` revierta a `False` un requisito que ya estaba `satisfied=True`, causando que el loop reintente indefinidamente una skill que ya cumplió su parte.
> **Caso reproducido:** requisito `data` satisfecho en iteración 0 por `busqueda_propiedades` → iteración 1 ejecuta `formatear_propiedades` → el requisito `data` vuelve a marcarse pendiente → el loop reintenta `formatear_propiedades` hasta `max_iterations` sin necesidad.
> **Principio de diseño:** el estado de "requisito cumplido" es un hecho acumulado a lo largo del loop, no una foto del último paso. Una vez que algo se cumplió, ningún paso posterior debería poder "des-cumplirlo" — es información que solo puede sumar, nunca restar.

---

## 1. Diagnóstico de causa raíz

Dos fallas de diseño probables, no mutuamente excluyentes — conviene revisar el código real contra ambas antes de aplicar el fix:

### 1.1 Falta de mapeo explícito skill → tipo de requisito

Si `_update_requirements_status()` evalúa "¿hay datos de propiedades en este resultado?" contra **cualquier** step, sin filtrar primero si esa skill es del tipo que puede satisfacer ese requisito, entonces al pasarle el resultado de `formatear_propiedades` (HTML de presentación, no una lista de propiedades) el chequeo da negativo — y ese negativo se interpreta como "el requisito ya no está cumplido".

### 1.2 Estado no monotónico (la causa más probable del síntoma exacto que describes)

Si la función hace algo del tipo:

```python
# SOSPECHOSO — sobreescribe sin verificar el estado anterior
requirement.satisfied = check_result
```

en vez de:

```python
# CORRECTO — solo permite pasar de False a True, nunca al revés
if check_result:
    requirement.satisfied = True
```

...entonces cualquier paso que no aporte evidencia para un requisito específico termina "limpiando" el estado anterior en vez de simplemente no tocarlo.

---

## 2. Fix: mapeo explícito + estado monotónico

**Ubicación:** `agents/base_agent.py` (o `agents/skill_preconditions.py` si ya centralizaste ahí la metadata de skills en el fix anterior)

### 2.1 Mapeo skill → tipo de requisito que puede satisfacer

```python
SKILL_SATISFIES_KIND: dict[str, str] = {
    'busqueda_propiedades': 'data',
    'busqueda_exacta': 'data',
    'matching_hibrido': 'data',
    'acm_analisis': 'data',
    'reporte_precios_zona': 'data',
    'mis_requerimientos': 'data',
    'matching_OD': 'data',
    'formatear_propiedades': 'format',
    'metricas_marketing': 'data',
    'campanas_activas': 'data',
}
```

Este mapeo ya lo tienes implícito en tu cabeza (sabes que `formatear_propiedades` es de formato y las demás son de datos) — el bug es que el código nunca lo hizo explícito, así que no puede filtrar por él.

### 2.2 `_update_requirements_status()` reescrito — monotónico y filtrado por tipo

```python
def _update_requirements_status(self, requirements: list[Requirement], step: AgentStep) -> None:
    """Actualiza el estado de los requisitos según el resultado de UN step.

    Reglas invariantes:
    1. MONOTÓNICO: un requisito satisfied=True nunca vuelve a False.
    2. FILTRADO POR TIPO: un step solo puede afectar requisitos cuyo 'kind'
       coincide con lo que esa skill puede satisfacer (sección 2.1).
    3. Un step fallido (AgentStatus.FAILED) nunca satisface nada.
    """
    if step.status == AgentStatus.FAILED or not step.skill_used:
        return  # nada que actualizar; en particular, NO se toca ningún requisito

    skill_kind = SKILL_SATISFIES_KIND.get(step.skill_used)
    if skill_kind is None:
        return  # skill sin mapeo conocido: no se asume nada sobre qué satisface

    has_valid_result = bool(step.skill_result)
    if not has_valid_result:
        return  # regla 1 aplicada implícitamente: no hay evidencia, no se toca nada

    for requirement in requirements:
        if requirement.satisfied:
            continue  # regla 1: ya estaba cumplido, no se re-evalúa ni se toca
        if requirement.kind == skill_kind:
            requirement.satisfied = True
            requirement.satisfied_by_skill = step.skill_used
```

**Por qué esto resuelve el caso exacto:** en la iteración 0, `busqueda_propiedades` tiene `skill_kind='data'`, encuentra el requisito `kind='data'` no satisfecho, y lo marca `True`. En la iteración 1, `formatear_propiedades` tiene `skill_kind='format'` — el bucle `for requirement in requirements` ni siquiera evalúa el requisito `data` porque el `continue` de la regla 1 lo salta apenas ve que ya está `satisfied=True`, y aunque no lo saltara, el chequeo `requirement.kind == skill_kind` ('data' == 'format') sería falso de todas formas. Doble protección, no solo una.

### 2.3 Guardia adicional: la lista de `requirements` es un único objeto mutado, no reconstruido

Verificar en el código actual que `requirements` se cree **una sola vez** al inicio del loop (`extract_requirements()`) y se pase por referencia a `_think()` y `_observe()` en cada iteración — nunca se debe volver a llamar `extract_requirements()` dentro del loop, ni reconstruir la lista con un nuevo `list(...)` o deepcopy en algún punto intermedio. Si en algún lugar del código actual `requirements` se reasigna (por ejemplo, si `_observe()` retorna una nueva lista en vez de mutar la existente y el loop la reemplaza), eso también produciría pérdida de estado aunque el fix de la sección 2.2 esté bien aplicado.

```python
# en ReActLoopMixin.run() — confirmar que es EXACTAMENTE así:
requirements = self.extract_requirements(original_message)   # se crea UNA vez

for iteration in range(self.definition.max_iterations):
    thought = self._think(original_message, requirements, steps, context)   # mismo objeto
    ...
    self._update_requirements_status(requirements, step)   # muta in-place, no retorna una lista nueva
    observation = self._observe(original_message, step, requirements, steps, context)
    ...
```

---

## 3. Test unitario específico (obligatorio, no solo suite de regresión end-to-end)

Este bug es lo suficientemente sutil como para merecer un test aislado de la función, sin pasar por todo el loop ni por DeepSeek:

```python
def test_requisito_data_no_se_revierte_por_formatear():
    requirements = [
        Requirement(id="req_1", description="buscar terrenos", kind="data"),
        Requirement(id="req_2", description="formato carrusel", kind="format"),
    ]

    step_busqueda = AgentStep(
        iteration=0, thought="...", skill_used="busqueda_propiedades",
        skill_params={}, skill_result={"propiedades": [{"id": 1}]},
        status=AgentStatus.OBSERVING,
    )
    _update_requirements_status(requirements, step_busqueda)
    assert requirements[0].satisfied is True   # data cumplido

    step_formato = AgentStep(
        iteration=1, thought="...", skill_used="formatear_propiedades",
        skill_params={}, skill_result={"html": "<div>...</div>"},
        status=AgentStatus.OBSERVING,
    )
    _update_requirements_status(requirements, step_formato)

    # el punto central del test:
    assert requirements[0].satisfied is True   # data DEBE seguir cumplido
    assert requirements[1].satisfied is True   # format ahora también cumplido
```

Este test debe agregarse permanentemente al repo — es exactamente el tipo de regresión silenciosa que un test end-to-end podría no atrapar si cambia ligeramente el orden de ejecución en el futuro.

---

## 4. Observabilidad — hacer visible la transición de estado (para atrapar esta clase de bug más rápido la próxima vez)

Agregar un log explícito de transición, no solo el estado final:

```python
def _update_requirements_status(self, requirements, step):
    for requirement in requirements:
        was_satisfied = requirement.satisfied
        # ... lógica de la sección 2.2 ...
        if requirement.satisfied and not was_satisfied:
            logger.info(f"[ReAct] Requisito '{requirement.description}' recién cumplido por '{step.skill_used}'")
        elif was_satisfied and not requirement.satisfied:
            # esto NUNCA debería poder pasar tras el fix — si aparece, es un bug nuevo
            logger.error(f"[ReAct] ALERTA: requisito '{requirement.description}' se revirtió de cumplido a pendiente. Esto viola la invariante monotónica.")
```

Ese `logger.error` es intencional: si después del fix alguna vez se dispara, es una señal inequívoca de que algo rompió la invariante — mucho más rápido de detectar que releer logs de iteración buscando el patrón que describiste hoy.

---

## 5. Criterios de aceptación

- [ ] Test unitario de la sección 3 pasa.
- [ ] La consulta "terrenos en Cerro Colorado en carrusel" completa el loop en 2 iteraciones (búsqueda + formato), no llega a `max_iterations`.
- [ ] El log `logger.error` de reversión de estado (sección 4) nunca se dispara en la suite de regresión completa.
- [ ] Un requisito `data` satisfecho por `busqueda_exacta` tampoco se revierte al ejecutar `formatear_propiedades` después (mismo caso, skill de origen distinta).
- [ ] La lista `requirements` conserva identidad de objeto (`id(requirements)` idéntico) entre el inicio y el final del loop — test que lo confirma explícitamente.

---

## 6. Nota sobre el patrón que se está repitiendo

Vale la pena que lo notes: los últimos tres bugs (`_observe` solo miraba datos, `busqueda_exacta` sin precondición, y ahora esto) son todos variantes del mismo problema de fondo — **estado que se evalúa de forma aislada, sin memoria acumulada del progreso real de la tarea**. Cada fix ha ido agregando una pieza de memoria explícita al loop (checklist de requisitos, precondiciones de skill, y ahora monotonicidad). Esto no es casualidad: es la parte más difícil de construir un agente de verdad, y es normal que aparezca en capas — primero notas que "no completa todo", después que "se atasca en una opción inválida", después que "olvida lo que ya logró". Cada capa que agregas hace al sistema más robusto frente a la siguiente. Después de este fix, el patrón de bugs que deberías esperar ver (si aparece alguno) es distinto: probablemente relacionado con calidad de las respuestas o eficiencia, no con que el agente pierda el hilo de la tarea.
