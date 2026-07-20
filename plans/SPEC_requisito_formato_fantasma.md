# SPEC: Eliminación de Requisitos de Formato Fantasma — Propifai (PIL)

> **Objetivo:** evitar que `extract_requirements()` (LLM) invente requisitos de tipo `format` que no corresponden a ningún formato real soportado, dejando la responsabilidad de detectar formato **exclusivamente** en `detect_format_requirement()` (determinista, por keywords).
> **Caso reproducido:** "dame información de la propiedad de quinta natura" → `extract_requirements()` genera un requisito de formato "genérico" que no existe en el sistema → nunca se satisface → el agente prueba skills de datos irrelevantes intentando resolverlo → `max_iterations` → cae a LangGraph fallback.
> **Principio de diseño:** una misma responsabilidad no debe tener dos fuentes de verdad que puedan contradecirse. La detección de "qué formato pidió el usuario" ya tiene un mecanismo determinista y confiable (`FORMAT_KEYWORDS`) — el LLM de extracción de requisitos no debe poder generar ese tipo de requisito en absoluto.

---

## 1. Diagnóstico de causa raíz

### 1.1 Por qué aparece el requisito fantasma

`extract_requirements()` le pide al LLM que descomponga la consulta en requisitos atómicos, incluyendo `kind='format'` como una opción válida. Cuando el usuario no menciona ningún formato, el LLM —entrenado a ser "completo"— a veces interpreta que *toda* respuesta necesita presentarse de alguna forma, y genera un requisito de formato vago ("presentación clara", "formato genérico") que no mapea a ninguna de las tres opciones reales que soporta `formatear_propiedades` (`carrusel`, `matriz`, `lista`).

### 1.2 Por qué el guardrail actual no lo detecta

`detect_format_requirement()` (determinista) solo agrega un requisito de formato cuando encuentra una keyword real en el mensaje — funciona perfecto para prevenir falsos negativos (que el LLM no detecte un formato que sí se pidió). Pero no está diseñado para lo opuesto: **corregir un falso positivo que ya generó el LLM**. Las dos funciones conviven sin que ninguna tenga autoridad final sobre el otro.

### 1.3 Por qué el agente se atasca probando skills irrelevantes

Mirando tu log: tras satisfacer `data` en la iteración 0, el agente prueba `matching_hibrido` (iteración 1) y `acm_analisis` (iteración 4) — ninguna tiene relación con "presentar de forma clara". El LLM en `_think()` ve un requisito pendiente que no puede mapear a ninguna skill concreta, y como no tiene una opción mejor, prueba otras skills de datos con la esperanza de que alguna "cuente" como formato — nunca va a funcionar, porque el requisito no corresponde a nada ejecutable.

---

## 2. Fix — una sola fuente de verdad para requisitos de formato

### 2.1 `extract_requirements()`: prohibir `kind='format'` en el schema

**Ubicación:** `agents/base_agent.py`

```python
def extract_requirements(self, original_message: str) -> list[Requirement]:
    prompt = f"""
    Descompón esta consulta del usuario en requisitos atómicos que la respuesta final debe cumplir.

    IMPORTANTE — REGLA ESTRICTA SOBRE FORMATO:
    NO generes ningún requisito relacionado con CÓMO se presenta la información
    (formato visual, presentación, claridad, estructura de la respuesta).
    Eso se detecta por otro sistema, de forma automática, y NO es tu responsabilidad.
    Solo genera requisitos sobre QUÉ información se necesita, QUÉ filtros aplicar,
    o QUÉ comparación/análisis se pide — nunca sobre cómo debe verse la respuesta.

    Consulta: "{original_message}"

    Responde SOLO con JSON:
    {{"requirements": [
        {{"description": "...", "kind": "data|filter|comparison|other"}}
    ]}}
    """
    # 'format' YA NO es una opción válida en el enum del prompt
    response = LLMService._call_deepseek_api(messages=[{"role": "user", "content": prompt}])
    parsed = parse_json(response)["requirements"]
    return [Requirement(id=f"req_{i}", **r) for i, r in enumerate(parsed)]
```

### 2.2 Filtro defensivo: descartar cualquier `kind='format'` que el LLM genere de todas formas

Los LLMs no siempre respetan instrucciones del prompt al 100% — es el mismo principio que ya aplicamos con las precondiciones de skills (guardrails en código, no solo en el prompt). Nunca confíes solo en la instrucción:

```python
def extract_requirements(self, original_message: str) -> list[Requirement]:
    # ... llamada al LLM como en 2.1 ...
    parsed = parse_json(response)["requirements"]

    # Guardrail defensivo: si el LLM generó 'format' pese a la instrucción,
    # se descarta aquí — el único lugar autorizado para crear requisitos
    # de formato es detect_format_requirement() (sección 2.3).
    requirements = [
        Requirement(id=f"req_{i}", **r) for i, r in enumerate(parsed)
        if r.get('kind') != 'format'
    ]
    return requirements
```

### 2.3 Única fuente de verdad para formato: `detect_format_requirement()` sin cambios

Esta función ya existe y ya es correcta — no se modifica. Simplemente ahora es la **única** que puede introducir un requisito `kind='format'` en el sistema:

```python
# en ReActLoopMixin.run() — sin cambios respecto al spec original
requirements = self.extract_requirements(original_message)   # nunca trae 'format' ahora

format_needed = detect_format_requirement(original_message)   # única fuente de verdad
if format_needed:
    requirements.append(Requirement(id=f"req_{len(requirements)}",
                                     description=f"presentar en formato {format_needed}",
                                     kind='format'))
```

Con esto: si el usuario no mencionó ninguna keyword de formato, **no existe ningún requisito de formato en absoluto** — el agente termina en cuanto satisface `data`, exactamente el comportamiento correcto para "dame información de la propiedad de quinta natura".

### 2.4 Red de seguridad final en `_observe()` (por si aparece un caso no previsto)

Aunque 2.1 y 2.2 deberían eliminar el problema de raíz, se agrega una última capa defensiva: si por cualquier motivo futuro apareciera un requisito `kind='format'` cuya descripción no corresponde a ninguno de los formatos reales soportados, se auto-satisface en vez de bloquear el loop indefinidamente:

```python
FORMATOS_REALES = {'carrusel', 'matriz', 'lista'}

def _observe(self, original_message, step, requirements, steps_history, context) -> dict:
    self._update_requirements_status(requirements, step)

    format_req = next((r for r in requirements if r.kind == 'format' and not r.satisfied), None)
    if format_req:
        formato_valido = any(f in format_req.description.lower() for f in FORMATOS_REALES)
        if not formato_valido:
            # requisito de formato no ejecutable — no bloquear el loop por algo
            # que ninguna skill real puede satisfacer
            logger.warning(f"[ReAct] Requisito de formato no reconocido, auto-satisfecho: {format_req.description}")
            format_req.satisfied = True
        else:
            formatting_skills_called = [s.skill_used for s in steps_history if s.skill_used == 'formatear_propiedades']
            if not formatting_skills_called:
                return {'is_sufficient': False, 'pending_requirements': [format_req.description]}

    pending = [r for r in requirements if not r.satisfied]
    if not pending:
        return {'is_sufficient': True}
    return {'is_sufficient': False, 'pending_requirements': [r.description for r in pending]}
```

Este `logger.warning` es intencional, igual que el `logger.error` del spec de estado monotónico: si se dispara, es una señal de que el fix de 2.1/2.2 no está funcionando como debería y hay que revisar por qué el LLM sigue generando requisitos de formato pese a la instrucción y el filtro.

---

## 3. Por qué esto también resuelve los errores de `matching_hibrido` y `acm_analisis` en tu log

No hace falta ningún guardrail adicional para esas skills — son síntoma, no causa. Una vez que no existe el requisito fantasma, el `_think()` no tiene ningún requisito pendiente sin skill asociada que lo empuje a "probar cosas al azar". El agente termina en la iteración 0, apenas `busqueda_propiedades` encuentra la propiedad.

---

## 4. Test de regresión — casos obligatorios

```python
CASOS_REGRESION_FORMATO_FANTASMA = [
    {
        "query": "dame información de la propiedad de quinta natura",
        "requisitos_esperados": [{"kind": "data"}],   # NINGÚN requisito de formato
        "skills_esperadas": ["busqueda_propiedades"],   # termina en 1 skill, no 3-4
        "iteraciones_maximas_esperadas": 1,
    },
    {
        "query": "terrenos en cerro colorado en carrusel",
        "requisitos_esperados": [{"kind": "data"}, {"kind": "format"}],
        "skills_esperadas": ["busqueda_propiedades", "formatear_propiedades"],
    },
    {
        "query": "cuáles son las características del departamento en Cayma código PF-102",
        "requisitos_esperados": [{"kind": "data"}],
        "skills_esperadas": ["busqueda_propiedades"],
        "iteraciones_maximas_esperadas": 1,
    },
]
```

El primer caso es el que hoy falla — debe pasar de "cae a fallback tras 5 iteraciones" a "responde en 1 iteración" tras el fix.

---

## 5. Criterios de aceptación

- [ ] "dame información de la propiedad de quinta natura" resuelve en 1 iteración (`busqueda_propiedades` únicamente), sin caer al fallback de LangGraph.
- [ ] `extract_requirements()` nunca devuelve un `Requirement` con `kind='format'` — verificado con test unitario que mockea una respuesta de LLM que sí intenta generar uno, confirmando que el filtro de la sección 2.2 lo descarta.
- [ ] `detect_format_requirement()` sigue siendo la única función capaz de agregar un requisito `kind='format'` al sistema.
- [ ] El `logger.warning` de la sección 2.4 nunca se dispara en la suite de regresión completa (si se dispara, algo del fix 2.1/2.2 no está funcionando).
- [ ] Los 3 casos de la sección 4 pasan.

---

## 6. Nota sobre el patrón que se sigue repitiendo (y por qué este es distinto)

A diferencia de los bugs anteriores (todos sobre *pérdida* o *mal cálculo* de estado), este es un bug de **diseño de responsabilidades duplicadas**: dos mecanismos (LLM y keywords) podían generar la misma clase de dato sin que ninguno tuviera autoridad final. La lección general para el resto del sistema: cualquier información que tenga una forma determinista y confiable de detectarse (como el formato) no debería, además, dejarse en manos de un LLM "por si acaso" — el LLM debe encargarse solo de lo que genuinamente requiere razonamiento (qué datos buscar, qué comparar), y el código determinista de lo que es una regla fija y enumerable. Vale la pena revisar si `kind='filter'` o `kind='comparison'` tienen el mismo riesgo en el futuro, aunque hoy no haya evidencia de que lo tengan.
