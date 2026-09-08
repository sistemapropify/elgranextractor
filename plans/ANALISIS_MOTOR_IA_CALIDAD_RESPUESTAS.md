# Motor de IA de Calidad de Respuestas — Análisis Técnico

Ruta: `/analisis-crm/calidad-motor/`
Módulo Django: `lead_intelligence`
Versión del análisis: `context-v2` (constante `ANALYSIS_VERSION`)

Este documento analiza la estructura, funciones y flujo del motor que evalúa
automáticamente la calidad de las conversaciones de los leads del CRM usando un
modelo de lenguaje (DeepSeek), con una capa de análisis determinista previa y una
capa de validación estricta de evidencia posterior.

---

## 1. Vista general del flujo

```
CRM (dbpropify_be, solo SELECT)
   │  chat_history
   ▼
analyze_chat_history()  ──► análisis DETERMINISTA
   │  (estructura: mensajes, tiempos, interés, visitas, contacto)
   ▼
AnalizarConversacionLeadSkill  ──► anaálisis CONTEXTUAL con LLM (DeepSeek)
   │  analyze_conversation_context()
   ▼
Validación de evidencia (índices de mensajes reales del lead/agente)
   ▼
LeadConversationAssessment  ──► persistido en BD default
   │
   ▼
Dashboard "Calidad del motor IA"  +  Revisión humana + KPIs
```

Dos capas coexisten:

1. **Determinista** (`conversation_analysis.py`): heurística rápida sin costo en
   tokens (regex sobre texto normalizado). Se usa para obtener la *estructura*
   de la conversación y filtrar leads no analizables.
2. **Contextual con LLM** (`contextual_analysis.py`): clasificación semántica con
   DeepSeek, siempre respaldada por evidencia (índices de mensajes).

---

## 2. Rutas y vistas (URL / Vista)

Definidas en `webapp/analisis_crm/urls.py` → vistas en `webapp/lead_intelligence/views.py`.

| URL | Vista | Método | Función |
|-----|-------|--------|---------|
| `calidad-motor/` | `analysis_quality_dashboard` | GET | Dashboard de auditoría del motor |
| `calidad-motor/revisar/` | `conversation_review` | POST | Guarda revisión humana |
| `calidad-motor/ejecutar/` | `run_analysis` | POST | Dispara análisis IA (manual/Celery) |
| `calidad-motor/detener/` | `cancel_analysis` | POST | Cancela ejecución en curso |
| `calidad-motor/progreso/` | `analysis_progress_api` | GET | Progreso en vivo + modo histórico |

Todas protegidas con `@management_access_required`.

---

## 3. Funciones y responsabilidades

### 3.1 Vista del dashboard — `analysis_quality_dashboard`

`views.py:170`

- Lee parámetros de periodo vía `_parameters(request)`.
- Llama a `get_analysis_quality_dashboard(date_from, date_to)`.
- Añade `analysis_running` (si hay un run fresco en curso).
- Calcula costos IA por lead y resumen del periodo:
  - `get_ai_costs_by_lead(date_from, date_to)`
  - `ai_cost_summary(date_from, date_to, costs_by_lead)`
- Adjunta el costo IA (`ai_cost`) a cada ítem de la cola de revisión.
- Renderiza `lead_intelligence/analysis_quality_dashboard.html`.

### 3.2 Progreso en vivo — `analysis_progress_api` (`views.py:196`)

Es una API JSON con dos modos:

- **Modo en vivo** (default): devuelve el run en curso (o el del periodo, o el
  último global) con sus pasos (`AnalysisRunStep`) y KPIs de costo IA.
- **Modo histórico** (`?hist=1&from&to`): devuelve todos los runs del periodo con
  su `run_type`, `status`, contadores y pasos por lead.

### 3.3 Ejecución — `run_analysis` (`views.py:445`)

- Llama a `_has_fresh_running_run(clean_stale=True)` para evitar duplicados.
- Resetea la señal de cancelación.
- Si el broker de Celery es real (no `memory://`): encola
  `analizar_conversaciones_lead.delay(...)`.
- Si el broker es `memory://`: ejecuta el comando
  `analyze_lead_conversations` en un **hilo daemon** (`Thread`) para que el
  botón responda al instante y el progreso sea visible por latido.

### 3.4 Cancelación — `cancel_analysis` (`views.py:530`)

- Llama a `request_cancel()` para activar la señal cooperativa `_cancel_event`
  que corta el gasto de tokens sin matar el proceso.

### 3.5 Revisión humana — `conversation_review` (`views.py:411`)

- Valida `lead_id` y llama a `save_conversation_review(...)`.
- Persiste un `LeadConversationReview` en BD default. Sirve como *ground truth*
  para medir el acuerdo IA vs humano.

---

## 4. Capa determinista — `conversation_analysis.py`

Funciones principales:

| Función | Línea | Responsabilidad |
|---------|-------|-----------------|
| `normalize_text` | 66 | Normaliza minúsculas, acentos, espacios |
| `_message_content` | 73 | Extrae texto/adjuntos de un mensaje |
| `_has_useful_content` | 85 | Filtra mensajes vacíos/ruido |
| `_timestamp` | 98 | Normaliza timestamps a UTC |
| `has_interest` | 112 | Detecta interés comercial (regex) |
| `has_visit_intent` | 120 | Detecta intención de visita (regex) |
| `analyze_chat_history` | 155 | **Núcleo**: devuelve la estructura completa |

`analyze_chat_history` devuelve un dict con:
- `valid_json`, `is_null`, `empty_history`, `raw_useful_message_count`
- `total_messages`, `lead_messages`, `agent_messages`
- `first_response_seconds`, `contacted`, `bidirectional`
- `has_interest`, `qualified`, `visit_intent`
- `unattended`, `last_message_at`, `last_sender`
- `messages` (lista normalizada y deduplicada, ordenada por tiempo)

**Detalles clave**:
- Deduplica mensajes repetidos (misma emisor+texto+timestamp) de la ingesta
  Chatwoot/n8n.
- Timezone: convierte todo a UTC y usa `America/Lima` para fechas de cohorte.
- `qualified` se marca cuando hay interés + bidireccionalidad.

---

## 5. Capa contextual LLM — `contextual_analysis.py`

Constantes:
```python
ANALYSIS_VERSION = "context-v2"
VALID_DECISIONS = {"confirmed", "not_confirmed", "ambiguous"}
VALID_ATTENTION_DECISIONS = {"adequate", "partial", "inadequate", "not_applicable", "ambiguous"}
```

### 5.1 `conversation_hash` (línea 22)

SHA-256 del `chat_history`. Es la **clave de deduplicación**: si el hash no
cambia, no se re-evalúa (regla de oro para no gastar tokens).

### 5.2 `analyze_conversation_context` (línea 117)

Es el **corazón del motor**. Construye un `transcript` (lista de mensajes con
`message_index`) y un prompt `instructions` para el LLM con reglas estrictas:

- **qualified**: solo si el lead muestra interés comercial concreto.
- **visit_intent**: solo si el lead solicita/acepta visita o acuerda fecha; pedir
  precio/ubicación no basta.
- **evidence**: solo índices de mensajes del lead.
- **uncertainty**: ante duda, `ambiguous`/`not_confirmed`, nunca suponer.
- **attention_quality**: evalúa la primera respuesta del agente (quién propone,
  si responde directa y completamente, sin penalizar plantillas por repetirse).
- **explicit_request_rule**: solo solicitudes explícitas; no inventar lo que
  pidió el lead.
- **first_response_scope**: las omisiones de la PRIMERA respuesta no cambian
  retroactivamente por mensajes posteriores.
- **attention_scores**: relevancia, cobertura, directez, personalización.

Usa `LLMService.extract_structured_data(text, schema)` con hasta **3 intentos**.

### 5.3 Validación post-LLM (clave de la calidad)

Tras recibir el JSON del LLM, se valida:

- `_decision` / `_attention_decision`: normaliza a valores válidos.
- `_validated_evidence(...)`: verifica que los índices de evidencia apunten a
  mensajes **reales** del emisor correcto (`lead` o `agent`).
- Si `confirmed` sin evidencia → se degrada a `ambiguous`.
- Los índices de la primera respuesta del agente solo se aceptan si pertenecen
  al primer bloque real de respuesta (`_first_response_agent_indices`).
- `_confidence`: confianza acotada entre 0 y 1.
- `_optional_score`, `_string_list`: saneamiento de scores y listas.

> Esto protege contra **alucinaciones**: el LLM no puede afirmar una decisión si
> no hay un mensaje del lead que la respalde.

### 5.4 `AnalizarConversacionLeadSkill` — `intelligence/skills/analizar_conversacion_lead.py`

Es la **brida entre el pipeline y el skill abstracto** `BaseSkill`:

- `validate_params`: acepta `messages` (lista) o `lead_id`.
- `execute`: si recibe `lead_id`, obtiene la conversación vía
  `get_lead_conversation`; luego llama a `analyze_conversation_context(messages)`.
- Devuelve un `SkillResult` con `data=assessment` y metadatos de
  `analysis_version`/`model_version`.

---

## 6. Orquestación — comando `analyze_lead_conversations.py`

### Señales de cancelación

```python
_cancel_event = threading.Event()
request_cancel()   # .set()
reset_cancel()     # .clear()
is_cancel_requested()  # .is_set()
```

### `_process_row` (línea 101)

Procesa un lead de forma **independiente** (paralelizable):

1. Si cancelado → `cancelled`.
2. Bind a `trace_id=f"lead:{id}"` para el log de costo IA.
3. Calcula `history_hash`.
4. **Regla de oro**: si `(id, hash)` ya existe y `not force` → `skipped` (sin
   llamar a DeepSeek).
5. `analyze_chat_history` → si no hay mensajes → `skipped`.
6. Filtro por etapa mínima `_min_stage_ok(stages, structural)`.
7. `AnalizarConversacionLeadSkill().execute(...)` → si falla → `failed`.
8. Post-condiciones: si no hay bidireccionalidad, `qualified_status=not_confirmed`;
   si no hubo contacto, `first_response_status=not_applicable`.
9. Si `dry_run` → `analyzed` (sin escribir).
10. `update_or_create` en `LeadConversationAssessment` (BD default).

### `handle` (línea 206)

- **Criterio de selección de leads**:
  - `--lead-id`: un lead específico.
  - `--lookback-hours`: últimas N horas (canal incremental/tiempo real).
  - `--from/--to`: rango de fechas.
- **Tipos de ejecución** (`run_type`):
  - `INCREMENTAL`: lookback + `stages=bidirectional`.
  - `DAILY`: lookback sin bidirectional.
  - `MANUAL`: sin lookback.
- **Concurrencia**: `ThreadPoolExecutor(max_workers=workers)` con 1–8 workers.
- **Registro de run**: crea `AnalysisRun` (`running`) + controla `heartbeat_at`
  cada 5 leads procesados (para visibilidad de progreso y detección de procesos
  muertos/colgados).
- **Cierre**: marca `COMPLETED` o `FAILED` (si cancelado) con `error_summary`.

---

## 7. Modelos de datos (BD default)

| Modelo | Tabla | Propósito |
|--------|-------|-----------|
| `AnalysisRun` | `prometeo_analysis_run` | Ejecución de análisis (estado, contadores, tipo) |
| `AnalysisRunStep` | `prometeo_analysis_run_step` | Log en vivo por lead de cada run |
| `LeadConversationAssessment` | `prometeo_lead_conversation_assessment` | Evaluación IA por lead (status, confianza, evidencia, scores) |
| `LeadConversationReview` | `prometeo_lead_conversation_review` | Revisión humana (verdict correct/incorrect/unsure) |
| `AIConsumptionLog` | (intelligence) | Costo/tokens de cada llamada LLM |

### Índices y unicidad clave

- `LeadConversationAssessment`: **UniqueConstraint**
  `(source_lead_id, history_hash, analysis_version)` → garantiza una sola
  evaluación vigente por versión de motor.
- `LeadConversationReview`: **UniqueConstraint**
  `(source_lead_id, history_hash, analysis_version, stage)` → una revisión por
  etapa.

---

## 8. KPIs del dashboard — `get_analysis_quality_dashboard` (`services.py:1131`)

- **Cobertura**: `coverage_pct` = evaluados / analizables.
- **Decisiones por etapa**: `decision_counts` (qualified / visit_intent /
  first_response) con Counter por valor.
- **Distribución de confianza**: `confidence_buckets` (<60, 60–74, 75–89, ≥90).
- **Problemas de evidencia**: `evidence_issues` (decisión afirmativa sin
  evidencia válida).
- **Cola de revisión** (`review_queue`): leads que requieren atención por:
  - multimedia no observable (`media_gap_risk`)
  - la IA infirió solicitudes no expresadas (`unsupported_request_items`)
  - decisión ambigua
  - confianza < 75%
  - falta de evidencia válida
  - muestras de alta confianza (≥ 85%) sin revisar para control de calidad.
- **Concordancia IA-humano**: `agreement_pct`, `correct_reviews`, `incorrect_reviews`,
  `false_positives`, `false_negatives` (a partir de reviews decisivas).
- **Runs recientes**: últimos 10 con `progress_pct`.

---

## 9. Costo IA — `services.py:1888`

- `get_ai_costs_by_lead`: agrega `AIConsumptionLog` filtrando por
  `trace_id__startswith="lead:"` dentro del periodo, sumando `estimated_cost_usd`,
  `total_tokens` y contando `id`. Retorna `{lead_id: {cost_usd, tokens, calls}}`.
- `ai_cost_summary`: total USD, nº de leads con costo, promedio por lead.
- Nota de compatibilidad Azure SQL: el GROUP BY requiere `order_by("trace_id")`
  para evitar el error 8127.

---

## 10. Decisión de diseño destacada

El motor combina **"eficiencia"** con **"auditabilidad"**:

1. **Determinismo primero** (`conversation_analysis.py`) filtra sin costo y
   provee estructura.
2. **LLM solo cuando es necesario** (regla de oro del hash) → ahorro de tokens.
3. **Validación estricta de evidencia** post-LLM → mitiga alucinaciones.
4. **Revisión humana** (ground truth) → permite medir precisión y alimentar
   mejoras del prompt.
5. **Costo trazable por lead** (trace_id) → transparencia del gasto IA.

Este enfoque es autoevaluable: el propio dashboard audita al motor con KPIs
(acuerdo humano-IA, confianza, cobertura, problemas de evidencia).
