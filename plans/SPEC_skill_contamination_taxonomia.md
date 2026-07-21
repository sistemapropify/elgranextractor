# SPEC: Corrección de Skill Contamination vía Taxonomía de Requisitos — Propifai (PIL)

> **Objetivo:** evitar que `matching_hibrido` (y por extensión `acm_analisis`) se elijan para consultas que no los necesitan, sin recurrir a keyword matching sobre el texto del requisito (frágil, mismo error que ya corregimos en el Supervisor).
> **Caso reproducido:** "dame información de la propiedad de quinta natura" → `busqueda_propiedades` encuentra los datos (iteración 0) → el agente igual ejecuta `matching_hibrido` (iteración 1), que falla, y dispara un falso positivo de "cero resultados tras 2 intentos".
> **Corrige:** `SKILL_SATISFIES_KIND` (de `SPEC_estado_monotonico_requisitos.md`) y `extract_requirements()` (de `SPEC_requisitos_completos_react_loop.md`), no los reemplaza — refina su granularidad.

---

## 1. Por qué el Fix 4 que ya propusiste (keyword matching) no es la mejor solución

Tu propuesta original:

```python
if any(word in req_text for word in ['información', 'info', 'datos', 'detalles', 'ficha']):
    return SEARCH_SKILLS
if any(word in req_text for word in ['match', 'combinar', 'cruzar', 'oferta', 'demanda']):
    return SEARCH_SKILLS | MATCH_SKILLS
```

Este es el mismo mecanismo que reemplazamos en el Supervisor (`SPEC_supervisor_llm_routing.md`) precisamente porque colisiona con vocabulario no anticipado: "quiero cruzar esta propiedad con lo que busca mi cliente" no contiene "match" ni "combinar" tal cual, y quedaría mal clasificada. Cada vez que agregues una skill nueva vas a tener que volver a esta lista y adivinar qué palabras la activan — es deuda técnica recurrente, no una solución estructural.

**La solución mejor no es un tercer sistema de keywords — es afinar el sistema tipado que ya construimos.**

---

## 2. Diagnóstico de causa raíz (la real, no el síntoma)

`SKILL_SATISFIES_KIND` (spec de estado monotónico) agrupa demasiado:

```python
# ACTUAL — 3 propósitos distintos bajo la misma etiqueta 'data'
SKILL_SATISFIES_KIND = {
    'busqueda_propiedades': 'data',    # buscar inventario
    'busqueda_exacta': 'data',         # buscar inventario
    'matching_hibrido': 'data',        # ← cruzar oferta-demanda, NO es "buscar"
    'acm_analisis': 'data',            # ← comparar contra mercado, NO es "buscar"
}
```

Como las tres comparten `kind='data'`, y el requisito extraído también es `kind='data'`, **cualquiera de las tres parece igual de válida** para satisfacerlo — no hay forma de que el sistema distinga "necesito buscar" de "necesito cruzar" de "necesito comparar" si todas llevan la misma etiqueta.

---

## 3. Fix: refinar la taxonomía de `kind`

### 3.1 Nuevos valores de `kind` (más específicos)

```python
# Antes: 'data' | 'filter' | 'comparison' | 'other'
# Después:
KIND_VALUES = ('data', 'comparison', 'matching', 'filter', 'other')
# 'format' sigue prohibido para extract_requirements() — spec anterior sin cambios
```

- `data`: buscar/consultar inventario existente (lo que hace `busqueda_propiedades`, `busqueda_exacta`).
- `comparison`: análisis comparativo de mercado, reportes de precios (lo que hace `acm_analisis`, `reporte_precios_zona`).
- `matching`: cruzar requerimientos de clientes con oferta disponible (lo que hace `matching_hibrido`, `matching_OD`, `mis_matches`).
- `filter`, `other`: sin cambios respecto al spec original.

### 3.2 `SKILL_SATISFIES_KIND` reescrito con la granularidad correcta

**Ubicación:** `agents/base_agent.py`

```python
SKILL_SATISFIES_KIND = {
    'busqueda_propiedades': 'data',
    'busqueda_exacta': 'data',
    'mis_requerimientos': 'data',
    'mis_propiedades': 'data',
    'campanas_activas': 'data',

    'acm_analisis': 'comparison',
    'reporte_precios_zona': 'comparison',
    'metricas_marketing': 'comparison',

    'matching_hibrido': 'matching',
    'matching_OD': 'matching',
    'mis_matches': 'matching',

    'formatear_propiedades': 'format',
}
```

### 3.3 `extract_requirements()` — actualizar el enum del prompt

```python
def extract_requirements(self, original_message: str) -> list[Requirement]:
    prompt = f"""
    Descompón esta consulta del usuario en requisitos atómicos que la respuesta final debe cumplir.

    Usa estos tipos ('kind') según lo que el usuario realmente necesita:
    - "data": buscar o consultar propiedades existentes en el inventario.
    - "comparison": pedir un análisis de mercado, reporte de precios, o comparación de valor.
    - "matching": cruzar los requerimientos de un cliente con el inventario disponible.
    - "filter": aplicar un filtro específico sobre resultados ya obtenidos.
    - "other": cualquier otra cosa.

    IMPORTANTE: NO generes ningún requisito de tipo formato (cómo se presenta la información) —
    eso se detecta automáticamente por otro sistema y no es tu responsabilidad.

    Consulta: "{original_message}"

    Responde SOLO con JSON:
    {{"requirements": [{{"description": "...", "kind": "data|comparison|matching|filter|other"}}]}}
    """
    response = LLMService._call_deepseek_api(messages=[{"role": "user", "content": prompt}])
    parsed = parse_json(response)["requirements"]
    return [Requirement(id=f"req_{i}", **r) for i, r in enumerate(parsed) if r.get('kind') != 'format']
```

Para "dame información de la propiedad de quinta natura", esto genera **un solo requisito `kind='data'`** — nunca `matching` ni `comparison`, porque el usuario no pidió cruzar nada ni comparar nada.

### 3.4 Filtro de relevancia en `get_available_skills()` — la pieza que realmente resuelve el bug

**Ubicación:** `agents/skill_preconditions.py`

Esta es la extensión clave: una skill solo se ofrece como opción si existe al menos un requisito **pendiente** cuyo `kind` coincide con lo que esa skill satisface. Reutiliza exactamente el mismo `SKILL_SATISFIES_KIND` que ya usa `_update_requirements_status()` — una sola fuente de verdad para "qué skill sirve para qué", consumida en dos lugares (qué ofrecer, y qué marcar como cumplido).

```python
def get_available_skills(allowed_skills: list[str], steps_history: list["AgentStep"],
                          context: dict, requirements: list["Requirement"]) -> list[str]:
    # Paso 1: precondiciones existentes (sin cambios)
    disponibles = [
        s for s in allowed_skills
        if s not in SKILL_PRECONDITIONS or SKILL_PRECONDITIONS[s](steps_history, context)
    ]

    # Paso 2: exclusión por fallos repetidos (sin cambios)
    failure_counts = track_consecutive_failures(steps_history)
    disponibles = [s for s in disponibles if failure_counts.get(s, 0) < MAX_CONSECUTIVE_FAILURES]

    # Paso 3 (NUEVO): relevancia — solo ofrecer skills cuyo kind
    # corresponde a un requisito TODAVÍA PENDIENTE
    kinds_pendientes = {r.kind for r in requirements if not r.satisfied}
    disponibles = [
        s for s in disponibles
        if s not in SKILL_SATISFIES_KIND or SKILL_SATISFIES_KIND[s] in kinds_pendientes
    ]

    return disponibles
```

**Por qué esto resuelve el caso exacto sin keywords:** en la iteración 1, después de que `busqueda_propiedades` satisface el único requisito (`kind='data'`), `kinds_pendientes` queda vacío. `matching_hibrido` tiene `SKILL_SATISFIES_KIND['matching_hibrido'] = 'matching'`, que no está en `kinds_pendientes` — **no aparece como opción**. El LLM no puede elegirla porque no está en la lista, igual que ya hicimos con las precondiciones de `busqueda_exacta`.

**Nota importante — no rompe casos legítimos con múltiples requisitos del mismo tipo:** si la consulta fuera "búscame departamentos en Cayma y compáralos con el precio de mercado", `extract_requirements()` generaría un requisito `kind='data'` y otro `kind='comparison'` — ambos pendientes al inicio, así que tanto `busqueda_propiedades` como `acm_analisis` siguen disponibles desde la iteración 0. El filtro no bloquea skills necesarias, solo las que ya no tienen ningún requisito pendiente que justifique usarlas.

### 3.5 Actualizar la llamada en `ReActLoopMixin.run()`

```python
# antes
available = get_available_skills(self.definition.allowed_skills, steps, context)

# después — se pasa 'requirements' también
available = get_available_skills(self.definition.allowed_skills, steps, context, requirements)
```

---

## 4. Fix complementario: refinar el chequeo de "cero resultados" en `_observe()`

Con el fix de la sección 3, `matching_hibrido` ya no debería ejecutarse en este caso — pero como defensa adicional (y porque tu propio diagnóstico en la sección 6.5/8 de tu documento ya lo identificó correctamente), el conteo de "intentos de búsqueda sin resultados" debe usar solo skills de `kind='data'`, no todo lo que alguna vez estuvo bajo el paraguas genérico `DATA_SKILLS`:

```python
SEARCH_KINDS = {'data'}   # solo búsqueda de inventario cuenta para "cero resultados genuino"

def _observe(self, original_message, step, requirements, steps_history, context) -> dict:
    self._update_requirements_status(requirements, step)

    skill_kind = SKILL_SATISFIES_KIND.get(step.skill_used)
    if skill_kind in SEARCH_KINDS and _result_item_count(step.skill_result) == 0:
        intentos_busqueda = sum(
            1 for s in steps_history
            if SKILL_SATISFIES_KIND.get(s.skill_used) in SEARCH_KINDS
        )
        todos_vacios = all(
            _result_item_count(s.skill_result) == 0
            for s in steps_history
            if SKILL_SATISFIES_KIND.get(s.skill_used) in SEARCH_KINDS
        )
        if intentos_busqueda >= 2 and todos_vacios:
            return {'is_sufficient': True, 'final_answer_override': {'total': 0, 'mensaje': 'No se encontraron propiedades.'}}

    # resto sin cambios (checklist de requisitos pendientes)
    ...
```

Esto reemplaza el `DATA_SKILLS` plano del `ADDENDUM_formatear_propiedades_real.md` por un chequeo basado en `SKILL_SATISFIES_KIND`, consistente con el resto del sistema — una sola fuente de verdad para "qué skill hace qué", en vez de un tercer conjunto (`DATA_SKILLS`) que hay que mantener sincronizado a mano con `SKILL_SATISFIES_KIND`.

---

## 5. Qué pasa con tus Fixes 1-4 propuestos

| Tu propuesta | Qué hacer |
|---|---|
| Fix 1 (`SEARCH_SKILLS`/`MATCH_SKILLS`/`ANALYSIS_SKILLS`) | **Innecesario como conjunto nuevo** — ya lo reemplaza `SKILL_SATISFIES_KIND` refinado (sección 3.2), que cumple la misma función y ya existía. No crear un cuarto sistema de agrupación. |
| Fix 2 (contar solo búsquedas reales para "cero resultados") | **Correcto en el diagnóstico** — implementado en la sección 4, pero usando `SKILL_SATISFIES_KIND` en vez de un `SEARCH_SKILLS` nuevo. |
| Fix 3 (quitar `matching_hibrido` del prompt del agente) | **No hacer esto** — el fix de la sección 3.4 ya evita que se ofrezca cuando no corresponde, sin sacrificar la capacidad del agente de usarla cuando sí corresponde (ej. consulta de matching real). |
| Fix 4 (keyword matching sobre texto del requisito) | **Reemplazado** por el filtro de relevancia tipado de la sección 3.4 — mismo objetivo, sin la fragilidad de keywords. |

---

## 6. Test de regresión

```python
CASOS_REGRESION_SKILL_CONTAMINATION = [
    {
        "query": "dame información de la propiedad de quinta natura",
        "requisitos_esperados": [{"kind": "data"}],
        "skills_esperadas": ["busqueda_propiedades"],   # matching_hibrido NUNCA se ofrece
        "iteraciones_maximas_esperadas": 1,
    },
    {
        "query": "cruza mis requerimientos con las propiedades en Cayma",
        "requisitos_esperados": [{"kind": "data"}, {"kind": "matching"}],
        "skills_esperadas": ["busqueda_propiedades", "matching_hibrido"],  # aquí SÍ es relevante
    },
    {
        "query": "busca departamentos en Cayma y compáralos con el precio de mercado",
        "requisitos_esperados": [{"kind": "data"}, {"kind": "comparison"}],
        "skills_esperadas": ["busqueda_propiedades", "acm_analisis"],
    },
]
```

El segundo y tercer caso son los que confirman que el fix no es una prohibición de `matching_hibrido`/`acm_analisis` — solo las oculta cuando genuinamente no hay un requisito pendiente que las necesite.

---

## 7. Criterios de aceptación

- [ ] "dame información de la propiedad de quinta natura" resuelve en 1 iteración, sin ejecutar `matching_hibrido` ni `acm_analisis`.
- [ ] `matching_hibrido` nunca aparece en la lista de skills disponibles de `_think()` cuando no hay ningún requisito `kind='matching'` pendiente — verificable inspeccionando el prompt enviado.
- [ ] Los 3 casos de la sección 6 pasan, confirmando que el filtro habilita las skills correctas cuando sí son relevantes.
- [ ] El falso positivo de "cero resultados tras 2 intentos" no se dispara cuando `busqueda_propiedades` ya tuvo éxito, sin importar qué otra skill se haya intentado después.
- [ ] La latencia de "info de quinta natura" baja de ~42s a ~38-39s (se elimina la llamada extra a `_think()` + la ejecución fallida de `matching_hibrido`), medible con las métricas ya existentes.

---

## 8. Nota sobre consistencia con specs anteriores

Este fix modifica `SKILL_SATISFIES_KIND` (definido originalmente en `SPEC_estado_monotonico_requisitos.md`) y el enum de `kind` de `extract_requirements()` (definido en `SPEC_requisitos_completos_react_loop.md` y ajustado en `SPEC_requisito_formato_fantasma.md`). Al implementar, asegúrate de que tu MCP use **esta versión** de ambas estructuras como la definitiva — es un refinamiento acumulativo sobre las anteriores, no una versión en paralelo. Vale la pena, en este punto, considerar consolidar todos los specs y addendums en un solo documento final (como te ofrecí antes) para que no queden 6-7 archivos con definiciones parcialmente superpuestas de las mismas estructuras.
