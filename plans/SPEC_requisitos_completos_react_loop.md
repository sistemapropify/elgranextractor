# SPEC: Verificación de Requisitos Completos en el ReAct Loop — Propifai (PIL)

> **Objetivo:** corregir la terminación prematura del loop ReAct — el agente declara éxito con `is_sufficient=True` en cuanto una skill devuelve datos, sin verificar que TODOS los requisitos de la consulta original (incluyendo formato de presentación) quedaron cubiertos.
> **Caso reproducido:** "que terrenos tienes en cerro colorado y presentamelo en carrusel" → ejecuta `busqueda_propiedades`, encuentra datos, termina. Nunca llama `formatear_propiedades`. Respuesta sale en texto plano.
> **Principio de diseño:** así es como razona un agente que no pierde de vista la tarea completa — mantiene la solicitud original visible en cada paso y solo se detiene cuando la revisa contra un checklist explícito, no cuando un solo paso "salió bien".

---

## 1. Diagnóstico de causa raíz (dos problemas, no uno)

### 1.1 Problema confirmado: `_observe()` verifica existencia de datos, no cumplimiento de la consulta

```python
# ACTUAL — agents/base_agent.py
def _observe(self, original_message, step, context):
    has_data = bool(step.skill_result and len(step.skill_result) > 0)
    return {'is_sufficient': has_data, ...}
```

`is_sufficient` responde a "¿la última skill trajo algo?", no a "¿la respuesta que voy a dar cubre todo lo que pidió el usuario?". Con esta lógica, cualquier requisito que no dependa de "traer datos" (formato, orden, agrupación, comparación) queda invisible para el agente.

### 1.2 Problema no documentado pero de alto riesgo: pérdida del mensaje original entre iteraciones

```python
# ACTUAL — dentro de ReActLoopMixin.run()
for iteration in range(max_iterations):
    thought = self._think(message, context, steps)   # ← 'message' puede ya no ser el original
    ...
    message = self._build_next_message(...)           # ← se reasigna en cada vuelta
```

Si `_build_next_message()` no incluye literalmente la consulta original completa (solo resume "resultado del paso anterior"), el LLM en la iteración 2 puede perder de vista que el usuario pidió carrusel — no es solo que no lo verifica, es que puede que ya no lo "vea". Esto hay que confirmarlo mirando la implementación real de `_build_next_message()` antes de aplicar el fix de la sección 3, pero se corrige en el mismo cambio.

**Regla de diseño que resuelve ambos:** el mensaje original del usuario nunca se pierde ni se reemplaza durante el loop — se mantiene como una referencia fija (`original_message`), separada de cualquier mensaje de trabajo intermedio que se le pase al LLM en cada iteración.

---

## 2. Diseño: checklist de requisitos explícito

Esto es lo que hace que un agente no "olvide" partes de la tarea: en vez de evaluar cada paso de forma aislada, se extrae al inicio una lista explícita de requisitos atómicos de la consulta, y el loop no termina hasta que todos están marcados como cumplidos (o se alcanza `max_iterations`, en cuyo caso se informa qué quedó pendiente en vez de fingir que todo salió bien).

### 2.1 Nuevo paso: extracción de requisitos (una sola vez, al inicio del loop)

```python
@dataclass
class Requirement:
    id: str                    # ej. "req_1"
    description: str           # ej. "buscar terrenos en Cerro Colorado"
    kind: str                  # 'data' | 'format' | 'filter' | 'comparison' | 'other'
    satisfied: bool = False
    satisfied_by_skill: Optional[str] = None


def extract_requirements(self, original_message: str) -> list[Requirement]:
    """Descompone la consulta en requisitos atómicos verificables.
    Se llama UNA VEZ al inicio del loop, nunca se reescribe después."""
    prompt = f"""
    Descompón esta consulta del usuario en requisitos atómicos que la respuesta final debe cumplir.
    Cada requisito debe ser verificable de forma independiente.
    Presta especial atención a: formato de presentación solicitado (carrusel, lista, tabla, mapa),
    filtros específicos, comparaciones, y cualquier "y además" / "y también" en la consulta.

    Consulta: "{original_message}"

    Responde SOLO con JSON:
    {{"requirements": [
        {{"description": "...", "kind": "data|format|filter|comparison|other"}}
    ]}}
    """
    response = LLMService._call_deepseek_api(messages=[{"role": "user", "content": prompt}])
    return [Requirement(id=f"req_{i}", **r) for i, r in enumerate(parse_json(response)["requirements"])]
```

**Ejemplo real con la consulta del bug:**
```json
{"requirements": [
    {"description": "buscar terrenos disponibles en Cerro Colorado", "kind": "data"},
    {"description": "presentar el resultado en formato carrusel", "kind": "format"}
]}
```

### 2.2 Guardrail determinista de respaldo (código, no LLM) — principio ya establecido en tu arquitectura

Como ya definiste que "los guardrails de seguridad van en código, no en el prompt", este mismo principio aplica aquí: no confíes solo en que el LLM extraiga bien el requisito de formato. Agrega una verificación determinista de piso, barata y sin llamada a LLM:

```python
FORMAT_KEYWORDS = {
    'carrusel': 'carrusel',
    'en lista': 'lista',
    'en tabla': 'tabla',
    'matriz': 'matriz',
    'en mapa': 'mapa',
}

def detect_format_requirement(original_message: str) -> Optional[str]:
    """Detección determinista de respaldo — no depende de que el LLM
    haya extraído bien el requisito de formato en extract_requirements()."""
    msg_lower = original_message.lower()
    for keyword, formato in FORMAT_KEYWORDS.items():
        if keyword in msg_lower:
            return formato
    return None
```

Si `detect_format_requirement()` encuentra un formato pedido y `extract_requirements()` no generó un requisito `kind='format'` correspondiente, se agrega automáticamente — doble red de seguridad, igual que ya haces con `_validate_skill_access` para permisos.

### 2.3 `_observe()` reescrito: verifica contra el checklist completo, no contra el último paso

```python
def _observe(self, original_message: str, step: AgentStep, requirements: list[Requirement],
             steps_history: list[AgentStep], context: dict) -> dict:

    # 1. Marcar requisitos que esta skill específica pudo haber cumplido
    self._update_requirements_status(requirements, step)

    # 2. Verificación determinista de formato (guardrail de piso, sección 2.2)
    format_req = next((r for r in requirements if r.kind == 'format'), None)
    if format_req and not format_req.satisfied:
        formatting_skills_called = [s.skill_used for s in steps_history if s.skill_used == 'formatear_propiedades']
        if not formatting_skills_called:
            return {
                'is_sufficient': False,
                'reason': f"Falta cumplir: {format_req.description}",
                'pending_requirements': [r.description for r in requirements if not r.satisfied],
            }

    # 3. Verificación holística con LLM (como el paso final, no el único)
    pending = [r for r in requirements if not r.satisfied]
    if not pending:
        return {'is_sufficient': True, 'reason': 'todos los requisitos cumplidos'}

    return {
        'is_sufficient': False,
        'reason': f"{len(pending)} requisito(s) pendiente(s)",
        'pending_requirements': [r.description for r in pending],
    }
```

### 2.4 `_think()` actualizado: siempre ve la consulta original + el checklist pendiente

```python
def _think(self, original_message: str, requirements: list[Requirement],
           steps_history: list[AgentStep], context: dict) -> dict:

    pending = [r.description for r in requirements if not r.satisfied]
    completed = [r.description for r in requirements if r.satisfied]

    prompt = self.definition.system_prompt + f"""
    CONSULTA ORIGINAL DEL USUARIO (nunca cambia durante esta tarea):
    "{original_message}"

    REQUISITOS YA CUMPLIDOS:
    {completed or "ninguno todavía"}

    REQUISITOS PENDIENTES (debes seguir trabajando hasta cubrir todos):
    {pending}

    PASOS EJECUTADOS HASTA AHORA:
    {self._summarize_steps(steps_history)}

    SKILLS DISPONIBLES:
    {', '.join(self.definition.allowed_skills)}

    Si quedan requisitos pendientes, NO marques is_final=true todavía.
    Responde SOLO con JSON:
    {{"reasoning": "...", "is_final": true|false,
      "skill_name": "...", "params": {{...}},
      "final_answer": {{...}}, "confidence": 0.0-1.0}}
    """
    response = LLMService._call_deepseek_api(messages=[{"role": "user", "content": original_message}],
                                               system_prompt=prompt)
    return parse_json(response)
```

**Cambio clave respecto al código actual:** `original_message` se pasa siempre igual, nunca se reemplaza por un mensaje "resumido" de iteración a iteración (resuelve el problema 1.2). El progreso se comunica aparte, vía `completed`/`pending`, no reescribiendo la consulta.

### 2.5 `ReActLoopMixin.run()` reescrito

```python
class ReActLoopMixin:
    def run(self, original_message: str, context: dict) -> AgentResult:
        requirements = self.extract_requirements(original_message)

        # guardrail determinista de piso (sección 2.2)
        format_needed = detect_format_requirement(original_message)
        if format_needed and not any(r.kind == 'format' for r in requirements):
            requirements.append(Requirement(id=f"req_{len(requirements)}",
                                             description=f"presentar en formato {format_needed}",
                                             kind='format'))

        steps: list[AgentStep] = []

        for iteration in range(self.definition.max_iterations):
            thought = self._think(original_message, requirements, steps, context)

            if not self._validate_skill_access(thought.get('skill_name')):
                steps.append(AgentStep(iteration, thought['reasoning'], None, None, None, AgentStatus.FAILED))
                continue

            if not self._check_budget(self._accumulated_cost(steps)):
                return self._finalize_incomplete(steps, requirements, reason="presupuesto agotado")

            skill_result = None
            if thought.get('skill_name'):
                skill_result = SkillOrchestrator().execute_skill(
                    thought['skill_name'], thought.get('params', {}), context)

            step = AgentStep(iteration, thought['reasoning'], thought.get('skill_name'),
                              thought.get('params'), skill_result, AgentStatus.OBSERVING)
            steps.append(step)

            observation = self._observe(original_message, step, requirements, steps, context)

            if observation['is_sufficient'] and thought.get('is_final'):
                return AgentResult(self.definition.name, success=True,
                                    final_answer=thought.get('final_answer'),
                                    steps=steps, iterations_used=iteration + 1,
                                    confidence=thought.get('confidence', 0.0))
            # si no es suficiente, el loop continúa — _think() en la próxima vuelta
            # ve exactamente qué requisitos faltan (sección 2.4)

        return self._finalize_incomplete(steps, requirements,
                                          reason="max_iterations alcanzado con requisitos pendientes")

    def _finalize_incomplete(self, steps, requirements, reason: str) -> AgentResult:
        pending = [r.description for r in requirements if not r.satisfied]
        return AgentResult(self.definition.name, success=False, final_answer=None,
                            steps=steps, iterations_used=len(steps),
                            error_message=f"{reason}: {pending}", confidence=0.0)
```

**Nota sobre `_finalize_incomplete`:** cuando el agente no logra cumplir todos los requisitos dentro de `max_iterations`, no debe fingir éxito con una respuesta parcial silenciosa — el spec de autocrítica (fase 9 del refactor general) ya contempla este caso: un `AgentResult(success=False)` con requisitos pendientes explícitos es justo la señal que dispara el reintento de autocrítica o, si tampoco mejora, una respuesta que le avisa honestamente al usuario qué faltó.

---

## 3. Corrección del mapeo de filtros (bug secundario ya identificado en tu documento, sección 5.2)

Ya que estás tocando este código, corrige de paso el bug de nombres de campo que también documentaste: `detect_filters_from_query()` genera `{'tipo': 'terreno'}` pero `busqueda_exacta` espera `{'property_type_name': 'Terreno'}`.

```python
FIELD_NAME_MAP = {
    'tipo': 'property_type_name',
    'distrito': 'district_name',
    'precio_min': 'price_min',
    'precio_max': 'price_max',
    # completar con el resto de campos reales de la BD
}

def detect_filters_from_query(query: str) -> dict:
    raw_filters = _detect_raw(query)  # lógica actual sin cambios
    return {FIELD_NAME_MAP.get(k, k): v for k, v in raw_filters.items()}
```

No es la causa del bug del carrusel, pero es el mismo tipo de error silencioso (la skill "falla" sin que nadie se entere porque el loop no distingue "no encontré nada porque no hay terrenos" de "no encontré nada porque busqué con el campo equivocado") — vale la pena que `_observe()` también distinga estos dos casos en el futuro, pero no es parte obligatoria de este fix.

---

## 4. Observabilidad — extender `reasoning_steps`

Para que el checklist sea visible en el frontend (reutilizando el patrón ya existente):

```json
{
    "icon": "📋",
    "title": "Requisitos detectados",
    "description": "1) buscar terrenos en Cerro Colorado  2) presentar en formato carrusel",
    "type": "requirements_extracted",
    "order": 1
},
{
    "icon": "⏳",
    "title": "Requisito pendiente tras iteración 1",
    "description": "Falta: presentar en formato carrusel",
    "type": "requirement_pending",
    "order": 3
}
```

Esto también le da a tu job de recalibración nocturna (ya especificado) una señal mucho más rica que "thumbs down": puede agrupar fallas por tipo de requisito no cumplido (¿siempre falla en formato? ¿siempre en filtros?), no solo por agente/skill.

---

## 5. Suite de regresión — casos obligatorios

```python
CASOS_REGRESION_REQUISITOS = [
    {
        "query": "que terrenos tienes en cerro colorado y presentamelo en carrusel",
        "skills_esperadas_en_orden": ["busqueda_propiedades", "formatear_propiedades"],
        "formato_esperado": "carrusel",
    },
    {
        "query": "dame los departamentos en Cayma en una tabla",
        "skills_esperadas_en_orden": ["busqueda_propiedades", "formatear_propiedades"],
        "formato_esperado": "tabla",
    },
    {
        "query": "busca terrenos en Sachaca",  # sin requisito de formato explícito
        "skills_esperadas_en_orden": ["busqueda_propiedades"],
        "formato_esperado": None,  # no debe forzar formateo si no se pidió
    },
]
```

El último caso es importante: el fix no debe sobre-corregir y forzar `formatear_propiedades` siempre — solo cuando el checklist realmente lo requiere.

---

## 6. Criterios de aceptación

- [ ] La consulta "terrenos en cerro colorado y preséntamelo en carrusel" ejecuta `busqueda_propiedades` seguido de `formatear_propiedades` en el mismo loop, de forma consistente (10/10 corridas).
- [ ] `original_message` es idéntico en `_think()` en la iteración 1 y en la iteración N — verificado con un test que capture los prompts enviados a DeepSeek.
- [ ] Una consulta sin requisito de formato NO dispara `formatear_propiedades` innecesariamente (evita regresión de costo/latencia).
- [ ] Si el agente no logra cumplir todos los requisitos en `max_iterations`, `AgentResult.success=False` con el detalle de qué quedó pendiente — nunca una respuesta parcial disfrazada de éxito.
- [ ] `reasoning_steps` muestra el checklist de requisitos y su estado, visible en el dashboard.
- [ ] La suite de regresión de la sección 5 pasa al 100% antes de desplegar.

---

## 7. Nota de costo

Este fix agrega **una llamada más a DeepSeek por consulta** (`extract_requirements`, una sola vez al inicio del loop, no por iteración). Dado que tu latencia ya está en 64.6s con llamadas de ~2-5s cada una, esto suma otros 2-5s. Es aceptable porque reemplaza una clase de bug — respuesta incompleta sin que nadie se entere — que es más cara de detectar y corregir después que de prevenir aquí. Si en el futuro la latencia se vuelve crítica, `extract_requirements` es un buen candidato para un modelo más liviano (la tarea es clasificación/extracción simple, no generación compleja) — queda como optimización futura, no bloqueante para este fix.
