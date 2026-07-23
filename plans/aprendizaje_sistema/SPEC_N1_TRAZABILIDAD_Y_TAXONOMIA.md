# SPEC N1 — Trazabilidad confiable y taxonomía de errores

**Nivel:** 1  
**Tipo:** implementación inmediata  
**Modo:** observación solamente  
**Dependencias:** modelos actuales `SkillExecution`, `AgentExecution`,
`AIConsumptionLog`, `Conversation` y métricas existentes

---

## 1. Resultado esperado

Al terminar esta spec, una interacción podrá reconstruirse de extremo a extremo:

```text
request → routing → agente → skill → recuperación → LLM → respuesta → validaciones
```

El sistema podrá responder, mediante consulta y no leyendo logs:

- qué pidió el usuario;
- qué versión del sistema lo procesó;
- qué ruta tomó;
- qué datos recuperó;
- qué filtros aplicó;
- qué componente falló;
- si la respuesta quedó fundamentada;
- qué guardrail se activó;
- cuál fue el resultado final.

No se implementa detección estadística ni corrección automática en este nivel.

---

## 2. Problemas actuales que resuelve

1. `trace_id` existe en memoria/logs, pero no relaciona consistentemente todos los modelos.
2. `success=True` mezcla éxito técnico con corrección funcional.
3. Los errores viven en strings heterogéneos.
4. Los resultados vacíos, fallos SQL y respuestas no fundamentadas no tienen estados distintos.
5. `recalibrar_agentes` usa señales incompletas y puede cambiar configuración.
6. No existe un contrato único para analizar ejecuciones entre conversaciones.

---

## 3. Modelo de datos

### 3.1 Nuevo modelo `SystemTrace`

Archivo: `webapp/intelligence/models_learning.py` o sección separada de
`intelligence/models.py`.

```python
class SystemTrace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trace_id = models.CharField(max_length=64, unique=True, db_index=True)
    conversation = models.ForeignKey(
        Conversation, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='system_traces'
    )
    request_kind = models.CharField(max_length=50, db_index=True)
    normalized_query_hash = models.CharField(max_length=64, db_index=True)
    query_redacted = models.TextField(blank=True, default='')

    status = models.CharField(max_length=30, choices=[
        ('started', 'Started'),
        ('completed', 'Completed'),
        ('completed_empty', 'Completed empty'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
        ('blocked', 'Blocked by guardrail'),
    ], db_index=True)

    technical_success = models.BooleanField(default=False)
    grounded = models.BooleanField(null=True, blank=True, db_index=True)
    result_count = models.IntegerField(null=True, blank=True)
    orchestration_mode = models.CharField(max_length=50, blank=True, default='')
    code_version = models.CharField(max_length=64, blank=True, default='')
    config_version = models.CharField(max_length=64, blank=True, default='')
    embedding_version = models.CharField(max_length=64, blank=True, default='')
    latency_ms = models.IntegerField(null=True, blank=True)

    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
```

Índices:

- `(status, started_at)`;
- `(request_kind, started_at)`;
- `(grounded, started_at)`;
- `(code_version, config_version)`.

### 3.2 Nuevo modelo `SystemEvent`

```python
class SystemEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trace = models.ForeignKey(
        SystemTrace, on_delete=models.CASCADE, related_name='events'
    )
    sequence = models.IntegerField()
    event_type = models.CharField(max_length=80, db_index=True)
    component = models.CharField(max_length=100, db_index=True)
    outcome = models.CharField(max_length=30, db_index=True)
    error_code = models.CharField(max_length=80, blank=True, default='', db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['trace', 'sequence'],
                name='unique_event_sequence_per_trace',
            )
        ]
```

`payload` no puede contener prompts completos, claves, cookies ni respuestas completas.

### 3.3 Extender modelos existentes

Agregar `trace_id` indexado y nullable a:

- `SkillExecution`;
- `AgentExecution`;
- `AIConsumptionLog`.

Agregar `error_code` nullable a `SkillExecution` y `AgentExecution`.

No usar `EpisodicMemory` como fuente primaria: mezcla memoria de producto con
telemetría y pertenece al track de personalización.

---

## 4. Taxonomía inicial

### 4.1 Familias

| Familia | Código ejemplo | Significado |
|---|---|---|
| Infraestructura | `INFRA_TIMEOUT` | dependencia no respondió |
| Base de datos | `DB_TYPE_CONVERSION` | error de tipo SQL/JSON |
| Recuperación | `RETRIEVAL_EMPTY` | búsqueda válida sin resultados |
| Recuperación | `RETRIEVAL_FAILED` | la búsqueda no pudo completarse |
| Grounding | `UNGROUNDED_PROPERTY_CLAIM` | respuesta afirma propiedad sin evidencia |
| Grounding | `UNSUPPORTED_FIELD_CLAIM` | afirma campo no presente |
| Filtros | `EXACT_FILTER_VIOLATION` | resultado incumple filtro obligatorio |
| Routing | `WRONG_AGENT_ROUTE` | agente incompatible |
| Skills | `SKILL_PRECONDITION_FAILED` | skill ejecutada sin prerrequisito |
| Loop | `AGENT_LOOP_EXHAUSTED` | máximo de iteraciones |
| Formato | `INVALID_SKILL_RESULT_SCHEMA` | resultado no cumple contrato |
| Datos | `SILENT_EXTRACTION_FAILURE` | dato presente pero no extraído |
| Seguridad | `GUARDRAIL_BLOCKED` | salida bloqueada correctamente |

### 4.2 Severidad

- `critical`: dato inventado presentado como real, fuga o acción destructiva;
- `high`: resultado incorrecto que afecta decisión de negocio;
- `medium`: degradación recuperable o resultado incompleto;
- `low`: latencia, formato o ruido sin impacto funcional.

La severidad se calcula por reglas, no por el LLM.

---

## 5. Contrato de eventos

Eventos mínimos por trace:

1. `trace.started`;
2. `routing.completed` o `routing.failed`;
3. cero o más `agent.completed`;
4. cero o más `skill.completed`;
5. `retrieval.completed` cuando aplique;
6. `grounding.validated` cuando la respuesta contiene datos de propiedades;
7. `trace.completed`.

Payload mínimo de `retrieval.completed`:

```json
{
  "collection_names": ["propiedadespropify"],
  "query_hash": "sha256...",
  "filters": {
    "district": "Cayma",
    "property_type": "Departamento",
    "price_max": 160000
  },
  "result_count": 4,
  "document_ids": ["uuid-1", "uuid-2", "uuid-3", "uuid-4"],
  "field_presence": {
    "price": 4,
    "parking": 1
  }
}
```

No guardar embeddings ni contenido completo.

---

## 6. Componentes a crear

### `intelligence/learning/taxonomy.py`

- enums de familia, código, severidad y outcome;
- validación de combinaciones;
- mapeo temporal desde excepciones conocidas.

### `intelligence/learning/events.py`

- `start_trace(...)`;
- `emit_event(...)`;
- `complete_trace(...)`;
- secuencia transaccional;
- no lanzar excepciones al flujo principal;
- contador de eventos descartados.

### `intelligence/learning/redaction.py`

- reemplazar teléfonos, emails, tokens, cookies y credenciales;
- truncar textos;
- hash estable de consulta normalizada;
- allowlist de claves permitidas en payload.

### `intelligence/learning/grounding.py`

En Nivel 1 implementa invariantes simples:

- si `result_count == 0`, una respuesta no puede contener tarjetas o IDs de propiedades;
- todo `property_id` mencionado debe pertenecer a `document_ids`;
- precios numéricos mostrados deben existir en los campos recuperados;
- campos no presentes se marcan como “no registrados”.

No usar un LLM como verificador primario.

### Comando `audit_learning_telemetry`

Opciones:

```text
--since-hours 24
--fail-on-coverage-below 0.98
--json
```

Salida:

- traces iniciadas/finalizadas;
- huérfanas;
- cobertura de agentes, skills, retrieval y LLM;
- eventos inválidos;
- distribución por estado;
- payloads rechazados por redacción.

---

## 7. Puntos de instrumentación

1. `ChatProcessor.process_message`: crear y finalizar trace.
2. `AgentGraphBuilder`: eventos de routing y agente.
3. `SkillOrchestrator.execute_skill`: enlazar `SkillExecution`.
4. `RAGService.search_dynamic` y búsqueda de propiedades: evento de recuperación.
5. `LLMService._call_deepseek_api`: enlazar consumo, no almacenar prompt completo.
6. Formatter y guardrails: resultado de grounding.
7. Manejador superior de excepciones: finalizar trace fallida.

El mismo `trace_id` debe viajar mediante `ExecutionContext`, no regenerarse en cada capa.

---

## 8. Versionado

Registrar en cada trace:

- `code_version`: SHA del commit o `BUILD_VERSION`;
- `config_version`: hash de prompts, thresholds y routing;
- `embedding_version`: modelo + versión de corpus/índice;
- `schema_version`: versión del contrato de eventos.

Si no puede determinarse una versión, usar `unknown` y contabilizarlo como deuda.

---

## 9. Cambios de seguridad obligatorios

1. `recalibrar_agentes` debe exigir `--apply` explícito además de no usar `--dry-run`.
2. En producción, `--apply` queda deshabilitado por feature flag:
   `LEARNING_ALLOW_CONFIG_MUTATION=false`.
3. Retención inicial: 30 días para eventos detallados, 180 días para agregados.
4. No incluir `user_id` en firmas de patrones ni análisis.
5. Acceso al dashboard solo para rol técnico autorizado.

---

## 10. Orden de implementación

1. Crear enums y schemas.
2. Crear migraciones de modelos.
3. Crear redactor y pruebas.
4. Instrumentar `ChatProcessor`.
5. Propagar `trace_id` a agentes, skills y LLM.
6. Instrumentar retrieval y grounding.
7. Crear comando de auditoría.
8. Crear dashboard mínimo.
9. Ejecutar siete días en shadow.
10. Corregir huecos hasta alcanzar el gate.

---

## 11. Pruebas

### Unitarias

- redacción de teléfono, email y tokens;
- payload rechazado por clave no permitida;
- secuencia única de eventos;
- clasificación de excepciones;
- grounding con cero resultados;
- grounding de precio no soportado;
- el fallo de telemetría no rompe el chat.

### Integración

- consulta de propiedad exitosa;
- búsqueda vacía;
- error SQL;
- timeout de DeepSeek;
- fallo de skill con fallback;
- AgentGraph y LangGraph producen la misma estructura mínima.

### No funcionales

- overhead p95 < 20 ms excluyendo persistencia asíncrona;
- pérdida de eventos < 2 %;
- payload medio < 8 KB;
- no aparición de patrones de secretos en una muestra de eventos.

---

## 12. Criterios de aceptación

- ≥ 98 % de traces finalizadas;
- ≥ 95 % de ejecuciones correlacionadas;
- < 1 % de eventos inválidos;
- 100 % de búsquedas de propiedades con `result_count`;
- 100 % de respuestas con propiedades sometidas a grounding determinista;
- cero mutaciones automáticas;
- siete días estables.

Solo entonces se habilita el Nivel 2.

---

## 13. Rollback

Toda instrumentación se controla con:

```text
LEARNING_TELEMETRY_ENABLED
LEARNING_GROUNDING_AUDIT_ENABLED
```

Desactivar telemetría no debe desactivar los guardrails existentes. Las tablas
nuevas se conservan; no se eliminan durante rollback.

