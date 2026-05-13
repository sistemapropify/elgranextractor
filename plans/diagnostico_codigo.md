# Diagnóstico de Código — Sistema de Inteligencia Propifai

> **Fecha:** 2026-05-11
> **Analista:** Arquitecto de Software Senior
> **Propósito:** Identificar problemas estructurales, inconsistencias y deuda técnica con números de línea exactos.

---

## Resumen Ejecutivo

Se identificaron **17 problemas** clasificados en:
- **4 Críticos** — Causan fallos funcionales en producción
- **7 Medios** — Degradan la experiencia del usuario o la mantenibilidad
- **6 Leves** — Deuda técnica acumulada

---

## 🔴 PROBLEMAS CRÍTICOS

### C1. Pipeline siempre ejecuta `resolver_contexto` incluso sin contexto previo

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py:1209-1237)
**Líneas:** 1209-1237

```python
# Siempre construye pipeline con resolver_contexto primero
if ctx.skill_name == 'busqueda_propiedades':
    contexto_activo = cls._get_contexto_activo(ctx.conversation)  # Puede ser {}
    historial = cls._get_historial_mensajes(ctx.conversation)

    pipeline_steps = [
        SkillPipelineStep(name='resolver_contexto', ...),  # ← Siempre se ejecuta
        SkillPipelineStep(name='busqueda_propiedades', ...),
    ]
```

**Problema:** En el primer mensaje de una conversación (sin contexto previo), `_get_contexto_activo()` retorna `{}` y el historial tiene 0-1 mensajes. Aun así, se ejecuta `resolver_contexto` que consume una llamada DeepSeek innecesaria (~500ms-1s de latencia adicional) y puede introducir ruido.

**Impacto:** Latencia innecesaria en el primer turno. Posibilidad de que `resolver_contexto` genere parámetros espurios a partir de contexto vacío.

---

### C2. `_KEYWORDS_PROPIEDADES` incompleto — omite términos semánticos clave

**Archivo:** [`webapp/intelligence/skills/registry.py`](webapp/intelligence/skills/registry.py:25-38)
**Líneas:** 25-38

```python
_KEYWORDS_PROPIEDADES = frozenset({
    'casa', 'casas', 'departamento', 'departamentos', 'terreno', 'terrenos',
    'propiedad', 'propiedades', 'alquiler', 'venta', 'precio', 'precios',
    'cuarto', 'cuartos', 'habitacion', 'habitaciones', 'dormitorio',
    'dormitorios', 'banio', 'banos', 'estacionamiento', 'estacionamientos',
    'cochera', 'cocheras', 'metro', 'metros', 'area', 'areas',
    'construido', 'construida', 'construccion', 'edificio', 'edificios',
    'local', 'locales', 'oficina', 'oficinas', 'cayma', 'yanahuara',
    'cercado', 'miraflores', 'sachaca', 'cerro', 'colorado',
})
```

**Problema:** Faltan términos críticos para búsqueda semántica:
- `'construir'`, `'colegio'`, `'escuela'`, `'educacion'`, `'universidad'` — El usuario preguntó "donde pueda construir un colegio" y el sistema no detectó como búsqueda de propiedades
- `'comercial'`, `'industria'`, `'industrial'` — Usos de suelo
- `'remodelado'`, `'estreno'`, `'oportunidad'` — Términos de marketing inmobiliario
- `'precio'` ya está, pero falta `'presupuesto'`, `'rango'`

**Impacto:** Mensajes con intención clara de búsqueda de propiedades no son detectados por `find_best_skill()`, cayendo al flujo RAG puro que no tiene acceso a los filtros estructurados.

---

### C3. `pipeline_data[key] = result.data` pierde la estructura del resultado

**Archivo:** [`webapp/intelligence/skills/orchestrator.py`](webapp/intelligence/skills/orchestrator.py:352-354)
**Líneas:** 352-354

```python
if result.success:
    key = step.result_key or step.name
    pipeline_data[key] = result.data  # ← Solo almacena .data, pierde metadata
```

**Problema:** `result.data` para `busqueda_propiedades` es una `List[Dict]` (lista de field_values). El pipeline almacena solo esta lista, perdiendo:
- `result.metadata` (contiene `total_count`, `search_mode`, `collections_used`, etc.)
- `result.error_message` (si hay errores parciales)
- La estructura original del `SkillResult`

**Impacto:** En [`chat_processor.py:1255`](webapp/intelligence/services/chat_processor.py:1255), el código debe hacer `isinstance(resultado_busqueda_raw, list)` para determinar el formato, lo que es frágil. Si en el futuro `result.data` cambia de formato, se rompe silenciosamente.

---

### C4. Dos sistemas de detección de skills paralelos e inconsistentes

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py:748-867)
**Líneas:** 748-867

```python
def _infer_skill_request(cls, ctx, intent, trace_id):
    # ── 1. Intentar con el nuevo SkillRegistry ──
    best_skill = registry.find_best_skill(ctx.message, user_level=user_level)
    if best_skill:
        # ... usa SkillRegistry ...
        return cls._process_skill_request(ctx, trace_id)

    # ── 2. Fallback al sistema de skills antiguo ──
    candidate_skill = cls._find_skill_candidate(ctx.message)
    if not candidate_skill:
        return None
    # ... usa sistema antiguo ...
```

**Problema:** Existen dos mecanismos de detección:
1. **SkillRegistry** (nuevo, basado en keywords + scoring) — líneas 762-799
2. **`_find_skill_candidate`** (antiguo, basado en `search_skills` + heurísticas) — líneas 839-867

Ambos pueden detectar skills diferentes para el mismo mensaje. No hay unificación. El sistema antiguo (`_find_skill_candidate`) usa `SKILL_SYSTEM.registry.search_skills()` que a su vez usa el mismo `SkillRegistry`, pero con lógica de scoring diferente.

**Impacto:** Comportamiento impredecible. Dependiendo de qué sistema detecte primero, la respuesta puede ser completamente diferente.

---

## 🟡 PROBLEMAS MEDIOS

### M1. `_get_contexto_activo()` tiene dos fuentes de verdad

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py:1089-1144)
**Líneas:** 1089-1144

```python
# 1. Buscar en SkillExecution
ultima_ejecucion = SkillExecution.objects.filter(
    conversation=conversation,
    skill_name='busqueda_propiedades',
    status='success',
).order_by('-executed_at').first()

# 2. Fallback: buscar en metadata de la conversación
metadata = conversation.metadata or {}
contexto_guardado = metadata.get('contexto_activo_busqueda', {})
```

**Problema:** El contexto activo se guarda en dos lugares:
- `SkillExecution.parameters` (cuando se ejecuta `busqueda_propiedades` vía orchestrator)
- `conversation.metadata['contexto_activo_busqueda']` (cuando `_guardar_contexto_activo()` se llama explícitamente)

Ambos pueden desincronizarse. Si `SkillExecution` se crea sin `conversation` (como ocurría antes del Fix 4), el fallback a metadata funciona, pero si metadata está desactualizada, se pierde el contexto.

**Impacto:** Contexto perdido entre turnos de conversación cuando las dos fuentes divergen.

---

### M2. `_guardar_contexto_activo()` guarda parámetros sin normalizar

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py:1168-1179)
**Líneas:** 1168-1179

```python
@classmethod
def _guardar_contexto_activo(cls, conversation, contexto):
    if not contexto:
        return
    metadata = conversation.metadata or {}
    metadata['contexto_activo_busqueda'] = contexto  # ← Guarda RAW
    conversation.metadata = metadata
    conversation.save(update_fields=['metadata'])
```

**Problema:** Guarda el contexto exactamente como lo devuelve `resolver_contexto`, sin normalizar nombres de campos. Por ejemplo, si `resolver_contexto` devuelve `{'distrito': 'Cayma'}` en un turno y `{'district': 'Cayma'}` en otro (porque el schema cambió), se pierde la herencia de contexto.

**Impacto:** Inconsistencia en la herencia de filtros entre turnos.

---

### M3. `_process_skill_request()` construye ExecutionContext sin `timeout`

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py:1189-1200)
**Líneas:** 1189-1200

```python
execution_context = ExecutionContext(
    user_id=str(ctx.user.id),
    session_id=ctx.conversation.session_id,
    conversation_id=str(ctx.conversation.id),
    permissions=(...),
    environment='production',
    metadata={...},
    # timeout NO está definido → usa None
)
```

**Problema:** `ExecutionContext` tiene campo `timeout` (definido en [`orchestrator.py:28`](webapp/intelligence/skills/orchestrator.py:28)) pero nunca se establece. El valor por defecto es `None`, lo que significa que las skills pueden ejecutarse indefinidamente.

**Impacto:** Si DeepSeek se cuelga o una consulta SQL es muy lenta, el pipeline no tiene timeout y puede dejar el worker de Celery bloqueado.

---

### M4. `_render_pipeline_response()` serializa JSON directamente al usuario

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py:1539-1557)
**Líneas:** 1539-1557

```python
rendered_steps = []
for step in pipeline_result.steps:
    name = step.get('name')
    if step.get('success'):
        rendered_steps.append(
            f"{name}: {json.dumps(step.get('result_data'), ensure_ascii=False)}"
        )
```

**Problema:** Cuando el pipeline falla (p.ej., `stop_on_error=True` y el primer skill falla), esta función serializa `result_data` como JSON crudo y lo devuelve al usuario. Esto fue exactamente el Bug #2 que se reportó.

**Impacto:** Usuarios ven JSON crudo en lugar de texto legible cuando hay errores en el pipeline.

---

### M5. `resolver_contexto` se ejecuta en pipeline incluso cuando no hay historial

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py:1209-1230)
**Líneas:** 1209-1230

El pipeline siempre incluye `resolver_contexto` como primer paso. En el primer mensaje de una conversación:
- `contexto_activo` = `{}` (vacío)
- `historial` = `[]` (vacío, o solo el mensaje actual)

`resolver_contexto` recibe contexto vacío y aún así se ejecuta, consumiendo una llamada DeepSeek.

**Impacto:** ~500ms-1s de latencia adicional en el primer mensaje. Costo de API innecesario.

---

### M6. `find_best_skill()` no considera el historial de la conversación

**Archivo:** [`webapp/intelligence/skills/registry.py`](webapp/intelligence/skills/registry.py:114-216)
**Líneas:** 114-216

```python
def find_best_skill(self, intent: str, user_level: int = 1) -> Optional[BaseSkill]:
```

**Problema:** El método solo recibe el mensaje actual (`intent`). No tiene acceso al historial de la conversación ni al contexto activo. Por lo tanto, no puede determinar si "solo departamentos" es una continuación de una búsqueda anterior.

**Impacto:** En mensajes de seguimiento como "solo departamentos" o "y en cayma", el SkillRegistry puede seleccionar la skill incorrecta porque no tiene contexto de la conversación.

---

### M7. `_save_post_process` no se ejecuta en flujo de skill pipeline

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py:1437-1444)
**Líneas:** 1437-1444

```python
if pipeline_result.success:
    message_id = cls._save_response(ctx.conversation, response_text)
    cls._save_post_process(
        ctx=ctx,
        response_text=response_text,
        memory_context=None,      # ← Siempre None
        rag_context=None,          # ← Siempre None
        intent=None,               # ← Siempre None
        trace_id=trace_id,
    )
```

**Problema:** Cuando se ejecuta el pipeline de skills, `_save_post_process` recibe `memory_context=None`, `rag_context=None`, `intent=None`. Esto significa que:
- No se guarda el episodio en memoria episódica con el contexto RAG usado
- No se extraen hechos de la conversación
- El intent detectado no se registra

**Impacto:** Pérdida de información para el aprendizaje del sistema. La memoria episódica no registra las búsquedas de propiedades.

---

## 🟢 PROBLEMAS LEVES

### L1. `_infer_skill_request()` tiene lógica duplicada para `resolver_contexto`

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py:774-799)
**Líneas:** 774-799

La línea 774 redirige `resolver_contexto` al pipeline, pero la línea 1209-1237 también construye el pipeline para `busqueda_propiedades`. Ambas secciones hacen esencialmente lo mismo pero con lógica duplicada.

---

### L2. `_KEYWORDS_PROPIEDADES` hardcodeado vs. configurable en BD

**Archivo:** [`webapp/intelligence/skills/registry.py`](webapp/intelligence/skills/registry.py:25-38)

Los keywords están hardcodeados como `frozenset`. No hay forma de agregar nuevos términos sin modificar el código. Deberían ser configurables desde la BD o desde settings.

---

### L3. `field_values` tiene múltiples nombres para el mismo campo

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py:1286-1347)

```python
titulo = (
    field_values.get('title')
    or field_values.get('titulo')
    or field_values.get('name')
    or field_values.get('nombre')
    or 'Sin título'
)
```

Cada campo tiene 3-4 variantes de nombre. Esto indica que no hay un schema unificado de field_values. Cada colección RAG puede tener nombres de campo diferentes.

---

### L4. `_get_contexto_activo()` filtra campos con lista hardcodeada

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py:1121-1125)

```python
campos_contexto = [
    'distrito', 'tipo_propiedad', 'operacion',
    'precio_min', 'precio_max', 'habitaciones', 'banos',
    'area_min', 'area_max', 'condicion', 'semantic_query',
]
```

Lista hardcodeada que debe mantenerse sincronizada con el schema de `busqueda_propiedades`. Si se agrega un nuevo campo al schema, también debe agregarse aquí.

---

### L5. `_process_skill_request()` mezcla responsabilidades

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py:1182-1537)

El método hace TODO:
1. Construye `ExecutionContext` (línea 1189)
2. Decide si ejecutar pipeline o skill directa (línea 1202)
3. Construye pipeline steps (línea 1213)
4. Ejecuta pipeline (línea 1232)
5. Extrae resultados (línea 1242)
6. Guarda contexto activo (línea 1250)
7. Formatea respuesta con DeepSeek (línea 1262-1431)
8. Guarda respuesta (línea 1436)
9. Post-procesa (línea 1437)
10. Construye ChatResult (línea 1445)

Son ~350 líneas para un solo método. Violación del principio de responsabilidad única.

---

### L6. `_save_post_process` recibe `None` en flujo de skills

**Archivo:** [`webapp/intelligence/services/chat_processor.py`](webapp/intelligence/services/chat_processor.py:1437-1444)

Ya documentado en M7, pero también es un problema de diseño: `_save_post_process` debería poder obtener el contexto RAG usado desde el pipeline result.

---

## 📊 TABLA RESUMEN

| ID | Tipo | Archivo | Líneas | Descripción |
|----|------|---------|--------|-------------|
| C1 | 🔴 Crítico | chat_processor.py | 1209-1237 | Pipeline siempre ejecuta resolver_contexto |
| C2 | 🔴 Crítico | registry.py | 25-38 | _KEYWORDS_PROPIEDADES incompleto |
| C3 | 🔴 Crítico | orchestrator.py | 352-354 | pipeline_data[key] pierde estructura |
| C4 | 🔴 Crítico | chat_processor.py | 748-867 | Dos sistemas de detección paralelos |
| M1 | 🟡 Medio | chat_processor.py | 1089-1144 | Dos fuentes de verdad para contexto |
| M2 | 🟡 Medio | chat_processor.py | 1168-1179 | Contexto guardado sin normalizar |
| M3 | 🟡 Medio | chat_processor.py | 1189-1200 | ExecutionContext sin timeout |
| M4 | 🟡 Medio | chat_processor.py | 1539-1557 | Pipeline fallback renderiza JSON crudo |
| M5 | 🟡 Medio | chat_processor.py | 1209-1230 | resolver_contexto sin historial |
| M6 | 🟡 Medio | registry.py | 114-216 | find_best_skill sin contexto conversacional |
| M7 | 🟡 Medio | chat_processor.py | 1437-1444 | _save_post_process sin contexto RAG |
| L1 | 🟢 Leve | chat_processor.py | 774-799 | Lógica duplicada resolver_contexto |
| L2 | 🟢 Leve | registry.py | 25-38 | Keywords hardcodeados |
| L3 | 🟢 Leve | chat_processor.py | 1286-1347 | Múltiples nombres para mismo campo |
| L4 | 🟢 Leve | chat_processor.py | 1121-1125 | Lista de campos hardcodeada |
| L5 | 🟢 Leve | chat_processor.py | 1182-1537 | Método con demasiadas responsabilidades |
| L6 | 🟢 Leve | chat_processor.py | 1437-1444 | Post-process sin contexto en pipeline |

---

## 🔗 RELACIÓN CON ERRORES REPORTADOS

| Error reportado | Causa raíz | Problemas relacionados |
|----------------|------------|----------------------|
| HTTP 500 con typos | DeepSeek no extrae params → `{}` → pipeline vacío | C1, M5 |
| JSON crudo en respuestas | `_render_skill_response` serializa directo | M4 |
| Contexto perdido entre turnos | SkillExecution sin conversation + metadata stale | M1, M2 |
| SkillRegistry elige skill incorrecta | resolver_contexto score > busqueda_propiedades | C4, M6 |
| DeepSeek ignora resultados | Resultados pasados como JSON, no como texto | C3 |
| No reconoce "construir un colegio" | Keywords incompletos | C2 |
