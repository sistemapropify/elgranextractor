# Arquitectura del Evaluador de Leads (Calidad del Motor IA)

> Propifai · Módulo `lead_intelligence` · App: `analisis_crm` (URL `/analisis-crm/calidad-motor/`)
> Este documento describe cómo se evalúan las conversaciones de leads con DeepSeek, cómo se audita la calidad, cómo se muestra en vivo el progreso y cómo se mide el costo por lead.

---

## 1. Propósito

El evaluador analiza el `chat_history` de cada lead del CRM y determina, con evidencia verificable:

- **Calificación comercial** (`qualified_status`): confirmado / no confirmado / ambiguo.
- **Intención de visita** (`visit_intent_status`): confirmado / no confirmado / ambiguo.
- **Calidad de la primera respuesta** (`first_response_status`): adecuada / parcial / inadecuada / no aplica / ambigua, con 4 puntajes (relevance, coverage, directness, personalization).

Es **incremental** (solo reanaliza lo que cambió), **idempotente** (hash + versión), **auditable** (revisión humana) y **medible** (costo IA por lead).

---

## 2. Arquitectura general

```mermaid
flowchart TD
  subgraph UI["Dashboard /analisis-crm/calidad-motor/"]
    A[analysis_quality_dashboard] --> B[get_analysis_quality_dashboard]
    C[run_analysis] --> D[Thread/ThreadPool]
    E[analysis_progress_api] --> F[AnalysisRun + AnalysisRunStep]
  end

  subgraph COMANDO["management command analyze_lead_conversations"]
    G[handle] --> H[ThreadPoolExecutor → _process_row]
    H --> I[analyze_chat_history (determinista)]
    I --> J[AnalizarConversacionLeadSkill]
    J --> K[analyze_conversation_context (LLM)]
  end

  K --> L[LLMService.extract_structured_data]
  L --> M[_call_deepseek_api → DeepSeek]
  M --> N[AIConsumptionLog.registrar_llamada + trace_context lead:{id}]

  B --> O[(BD default: prometeo_*)]
  D --> G
  F --> O
  N --> O
```

**Fuentes de datos**: el CRM (Azure SQL `propifai`, solo SELECT) entrega los `chat_history`; la app `default` (Azure SQL `propiextractor`) guarda evaluaciones, runs, pasos, revisiones y consumo IA.

---

## 3. Estructura de archivos

| Archivo | Rol |
|---|---|
| [`webapp/lead_intelligence/management/commands/analyze_lead_conversations.py`](webapp/lead_intelligence/management/commands/analyze_lead_conversations.py:1) | Comando que orquesta la evaluación masiva |
| [`webapp/lead_intelligence/conversation_analysis.py`](webapp/lead_intelligence/conversation_analysis.py:1) | Análisis **determinista** (regex) del chat |
| [`webapp/lead_intelligence/contextual_analysis.py`](webapp/lead_intelligence/contextual_analysis.py:1) | Análisis **contextual** con DeepSeek + validación de evidencia |
| [`webapp/intelligence/skills/analizar_conversacion_lead.py`](webapp/intelligence/skills/analizar_conversacion_lead.py:1) | Skill que envuelve el análisis contextual |
| [`webapp/intelligence/services/llm.py`](webapp/intelligence/services/llm.py:1) | `LLMService` (llamadas a DeepSeek, extracción estructurada) |
| [`webapp/intelligence/models.py`](webapp/intelligence/models.py:826) | `AIConsumptionLog` (consumo y costo de tokens) |
| [`webapp/intelligence/learning/trace_context.py`](webapp/intelligence/learning/trace_context.py:1) | Contexto de traza (`lead:{id}`) para costo por lead |
| [`webapp/lead_intelligence/models.py`](webapp/lead_intelligence/models.py:1) | `AnalysisRun`, `AnalysisRunStep`, `LeadConversationAssessment`, `LeadConversationReview`, `LeadEventResolution` |
| [`webapp/lead_intelligence/services.py`](webapp/lead_intelligence/services.py:1) | Agregación de dashboards + `get_ai_costs_by_lead`/`ai_cost_summary` |
| [`webapp/lead_intelligence/views.py`](webapp/lead_intelligence/views.py:1) | Vistas: dashboard, ejecutar, detener, progreso, revisión |
| [`webapp/analisis_crm/urls.py`](webapp/analisis_crm/urls.py:1) | Rutas del módulo |
| [`webapp/lead_intelligence/templates/lead_intelligence/analysis_quality_dashboard.html`](webapp/lead_intelligence/templates/lead_intelligence/analysis_quality_dashboard.html:1) | Template del dashboard (KPIs, terminal en vivo, cola de revisión) |

---

## 4. Modelos de datos (BD `default`)

### 4.1 Ejecuciones
- **`AnalysisRun`** ([models.py](webapp/lead_intelligence/models.py:5)): una corrida. `status` (running/completed/failed), `run_type` (incremental/daily/manual), `date_from/date_to`, contadores (`leads_total/analyzed/skipped/failed`), `heartbeat_at`, `rules_version`, `model_version`, `error_summary`.
- **`AnalysisRunStep`** ([models.py](webapp/lead_intelligence/models.py:38)): línea del terminal en vivo. `run` FK, `lead_id`, `status` (started/analyzed/skipped/failed/completed/cancelled), `message`, `created_at`.

### 4.2 Resultado por lead
- **`LeadConversationAssessment`** ([models.py](webapp/lead_intelligence/models.py:160)): la evaluación vigente de un lead. Claves de idempotencia `(source_lead_id, history_hash, analysis_version)`:
  - Decisiones: `qualified_status`, `visit_intent_status` (confirmed/not_confirmed/ambiguous).
  - Confianzas: `qualified_confidence`, `visit_intent_confidence`.
  - Evidencia: `qualified_evidence`, `visit_intent_evidence` (índices de mensajes del lead), `first_response_evidence`.
  - Primera respuesta: `first_response_status`, `first_response_confidence`, `relevance/coverage/directness/personalization_score`, `lead_request_items`, `answered/unanswered_request_items`, `attention_reason`.
  - Meta: `reason`, `model_version`, `analyzed_at`.

### 4.3 Auditoría humana
- **`LeadConversationReview`** ([models.py](webapp/lead_intelligence/models.py:229)): verdad humana. `stage` (qualified/visit_intent/first_response), `ai_value` vs `human_value`, `verdict` (correct/incorrect/unsure), `notes`, `reviewed_by`, clave única `(lead, hash, version, stage)`.
- **`LeadEventResolution`** ([models.py](webapp/lead_intelligence/models.py:280)): resolución de eventos del CRM (no forma parte del pipeline LLM; registro aparte).

### 4.4 Consumo IA
- **`AIConsumptionLog`** ([models.py](webapp/intelligence/models.py:826)): una fila por llamada a DeepSeek. `prompt_tokens`, `completion_tokens`, `total_tokens`, `estimated_cost_usd`, `trace_id`, `endpoint`, `caller_app`, `success`, `duration_ms`, `model_name`. El costo se calcula en [`registrar_llamada`](webapp/intelligence/models.py:929) con precios por 1M tokens configurables (`DEEPSEEK_PRICE_INPUT_PER_1M` / `DEEPSEEK_PRICE_OUTPUT_PER_1M`).

---

## 5. Flujo de ejecución (paso a paso)

### 5.1 Disparo
- `POST /analisis-crm/calidad-motor/ejecutar/` → [`run_analysis`](webapp/lead_intelligence/views.py:358):
  1. Lee periodo (`_parameters`) y `force`.
  2. Si ya hay un run fresco, rechaza (`_has_fresh_running_run(clean_stale=True)`).
  3. `reset_cancel()` limpia la señal de cancelación.
  4. Si el broker Celery es real (`analizar_conversaciones_lead.delay(...)`), encola; con `memory://` lanza un **Thread** que llama al comando (para que el botón responda al instante).
- `POST /analisis-crm/calidad-motor/detener/` → [`cancel_analysis`](webapp/lead_intelligence/views.py:443): marca runs activos como `failed` y activa la señal `request_cancel()` (detiene el gasto de tokens de forma cooperativa).

### 5.2 Comando `analyze_lead_conversations`
- **`handle`** ([comando](webapp/lead_intelligence/management/commands/analyze_lead_conversations.py:154)):
  1. Carga filas de leads con `_lead_result_rows(date_from, date_to)` (SELECT al CRM).
  2. Construye `existing_keys = {(lead_id, history_hash)}` de evaluaciones vigentes (para omitir sin `--force`).
  3. Crea `AnalysisRun` (running) y `AnalysisRunStep` "started".
  4. Procesa en paralelo con `ThreadPoolExecutor(max_workers=workers)`.
  5. Por cada `future` completado, crea un `AnalysisRunStep` y, cada 5 procesados, actualiza el `heartbeat_at`/contadores.
  6. Al final: `completed` o `failed` (si hubo cancelación) y un paso "Fin".

### 5.3 Procesamiento de un lead — `_process_row`
([comando](webapp/lead_intelligence/management/commands/analyze_lead_conversations.py:59)):
1. Chequea la señal de cancelación.
2. **`bind_trace_id(f"lead:{id}")`** → todas las llamadas LLM de este lead quedan etiquetadas (costo por lead).
3. `conversation_hash(chat_history)` → si ya existe con la misma versión y sin `force`, `skipped`.
4. `analyze_chat_history(chat_history)` → estructura determinista.
5. `AnalizarConversacionLeadSkill().execute({"messages": ...})` → evaluación LLM.
6. Corrige determinísticamente: si no fue bidireccional → `not_confirmed`; si no hubo contacto → `first_response_status = not_applicable`.
7. `update_or_create(LeadConversationAssessment, ...)` en transacción (BD default).
8. Devuelve `analyzed` / `skipped` / `failed`.

### 5.4 Señal de cancelación
- `_cancel_event = threading.Event()`; `request_cancel()`, `reset_cancel()`, `is_cancel_requested()` ([comando](webapp/lead_intelligence/management/commands/analyze_lead_conversations.py:26)). El hilo de cada lead la revisa antes de llamar a DeepSeek.

---

## 6. Análisis determinista — [`conversation_analysis.py`](webapp/lead_intelligence/conversation_analysis.py:1)

No usa LLM; da estructura y señales previas:

- `normalize_text(value)`: minúsculas, sin tildes, espacios colapsados.
- `_message_content(message)`: extrae texto de claves `text/content/body/caption` o marca `[attachment]`.
- `_has_useful_content(content)`: descarta vacíos/solo puntuación.
- `_timestamp(value)`: parsea y normaliza a UTC (naive → UTC).
- `has_interest(text)` / `has_visit_intent(text)`: regex de patrones de interés y de intención de visita (con negativos tipo "no me interesa").
- `_has_visit_proposal(text)` / `_is_affirmative(text)`: detectan propuesta del agente y aceptación del lead.
- `lima_date(value)` / `milestone_within_days(...)`: fechas en `America/Lima`.
- **`analyze_chat_history(raw_history)`** ([línea 155](webapp/lead_intelligence/conversation_analysis.py:155)): devuelve el dict de análisis:
  - Limpia/deduplica mensajes (mismo emisor+texto+timestamp) — arreglo de duplicados de ingestión.
  - Ordena cronológicamente.
  - Marca hitos: `first_lead_at`, `first_agent_response_at`, `first_response_seconds`, `contacted`, `bidirectional`, `interest_at`, `qualified_at`, `visit_intent_at`, `unattended`, `last_message_at`.
  - Devuelve `messages` normalizados `{sender, text, timestamp, position}`.

---

## 7. Análisis contextual LLM — [`contextual_analysis.py`](webapp/lead_intelligence/contextual_analysis.py:1)

- **`conversation_hash(raw_history)`** ([línea 22](webapp/lead_intelligence/contextual_analysis.py:22)): SHA-256 del chat (idempotencia).
- Helpers de saneado: `_confidence`, `_decision`, `_attention_decision`, `_optional_score`, `_string_list`, `_validated_evidence`, `_first_response_agent_indices`.
- **`analyze_conversation_context(messages)`** ([línea 117](webapp/lead_intelligence/contextual_analysis.py:117)):
  1. Construye el `instructions` (task + reglas + transcript completo).
  2. Define el `schema` JSON que debe devolver el modelo (decisiones, confianzas, índices de evidencia, scores, ítems de solicitud).
  3. Reintenta hasta **3 veces** `LLMService.extract_structured_data(text, schema)` (rompe al primer éxito).
  4. **Valida la evidencia**: si `qualified_status == confirmed` pero no hay índices de mensajes del lead, baja a `ambiguous`; igual con `visit_intent`; si `first_response` es adequate/partial/inadequate sin evidencia del agente, `ambiguous`.
  5. Devuelve el assessment con `model_version` y `analysis_version`.

---

## 8. Skill — [`analizar_conversacion_lead.py`](webapp/intelligence/skills/analizar_conversacion_lead.py:1)

- `AnalizarConversacionLeadSkill`: `name = "analizar_conversacion_lead"`, `category = "crm"`, `access_level = 3`, dominio `marketing`.
- `validate_params(params)`: requiere `messages` (lista) o `lead_id`.
- `execute(params, context)`: si viene `lead_id` sin mensajes, obtiene la conversación con `get_lead_conversation` (SELECT al CRM); luego llama `analyze_conversation_context(messages)` y devuelve `SkillResult.ok(data=assessment, ...)`.

---

## 9. LLM Service y costo — [`llm.py`](webapp/intelligence/services/llm.py:1)

- `LLMService.DEEPSEEK_MODEL` (por defecto `deepseek-v4-flash`; traduce `deepseek-chat`), `MAX_TOKENS`, `TEMPERATURE`, `API_KEY` desde entorno.
- **`extract_structured_data(text, schema)`** ([línea 1061](webapp/intelligence/services/llm.py:1061)): arma prompt de extracción JSON, llama `_call_deepseek_api(..., response_format={"type":"json_object"}, max_tokens=4096)` y extrae el JSON.
- **`_call_deepseek_api(messages, system_prompt, ...)`** ([línea 89](webapp/intelligence/services/llm.py:89)): hace `requests.post` a DeepSeek; en éxito y en los 3 casos de error llama `AIConsumptionLog.registrar_llamada(...)` con tokens y duración. No pasa `trace_id` explícito → `registrar_llamada` usa `current_trace_id()` como fallback.
- **`registrar_llamada`** ([models.py](webapp/intelligence/models.py:929)): calcula `estimated_cost_usd = prompt_tokens/1M*price_in + completion_tokens/1M*price_out` con precios por entorno.
- **`trace_context`** ([trace_context.py](webapp/intelligence/learning/trace_context.py:1)): `ContextVar` con `bind_trace_id(token)` / `release_trace_id` / `current_trace_id()`.

### Costo por lead (feature reciente, commit `f3b55b4`)
- En `_process_row` se hace `bind_trace_id(f"lead:{id}")` → cada llamada LLM de ese lead queda con `trace_id="lead:{id}"` en `AIConsumptionLog`.
- Agregación en [`services.py`](webapp/lead_intelligence/services.py:1887):
  - **`get_ai_costs_by_lead(date_from, date_to)`**: suma `estimated_cost_usd`/`total_tokens`/calls agrupado por `trace_id` (prefijo `lead:`) dentro del periodo → `{lead_id: {cost_usd, tokens, calls}}`.
  - **`ai_cost_summary(date_from, date_to)`**: total USD, nº leads con costo y promedio.
- Exposición: dashboard (`analysis_quality_dashboard`) y API en vivo (`analysis_progress_api` → `cost_total_usd`, `cost_leads`, `cost_avg_usd`).
- UI: contador "Costo IA" en el panel de progreso (actualizado por polling) y línea "Costo IA: $X · N tokens · M llamadas" por lead en la cola de revisión.

---

## 10. Vistas y rutas ([`urls.py`](webapp/analisis_crm/urls.py:1))

| Ruta | Vista | Función |
|---|---|---|
| `/analisis-crm/calidad-motor/` | `analysis_quality` | Dashboard de calidad del motor |
| `/analisis-crm/calidad-motor/ejecutar/` | `run_analysis` | Lanza la evaluación |
| `/analisis-crm/calidad-motor/detener/` | `cancel_analysis` | Cancela de forma cooperativa |
| `/analisis-crm/calidad-motor/progreso/` | `analysis_progress` | API JSON en vivo (terminal + contadores + costo) |
| `/analisis-crm/calidad-motor/revisar/` | `conversation_review` | Guarda revisión humana |

### Dashboard — [`analysis_quality_dashboard`](webapp/lead_intelligence/views.py:162)
- Obtiene `get_analysis_quality_dashboard(date_from, date_to)`.
- Añade `ai_costs_by_lead` y `ai_cost_summary` (costo IA del periodo).
- Adjunta `item["ai_cost"]` a cada caso de la cola de revisión (por `lead_id`).

### API en vivo — [`analysis_progress_api`](webapp/lead_intelligence/views.py:176)
- Resuelve el run (en curso → por periodo → último global).
- Devuelve `run` con contadores, `progress_pct`, timestamps y `cost_total_usd/cost_leads/cost_avg_usd`; y `steps` (últimos 400) para el terminal. El template la consulta cada 2 s.

### Agregación — [`get_analysis_quality_dashboard`](webapp/lead_intelligence/services.py:1131)
- Carga filas + `analyze_chat_history` por lead; define `analyzable_ids` (con mensajes) y `hashes`.
- Toma las evaluaciones vigentes (coinciden `analysis_version` y `history_hash`) y las revisiones humanas.
- Por cada `(lead, stage)` (qualified/visit_intent/first_response) arma la **cola de revisión** con motivos: ambigüedad, confianza < 75 %, sin evidencia válida, multimedia no observable, solicitudes inferidas sin sustento.
- Calcula KPIs: cobertura, pendientes, ambiguos, baja confianza, revisiones, errores confirmados (acuerdo humano vs IA).

---

## 11. Concurrencia y consistencia

- `ThreadPoolExecutor(workers=1..8)` procesa leads en paralelo; cada hilo cierra conexiones (`close_old_connections`) y usa `transaction.atomic(using="default")` al guardar.
- **Idempotencia**: `UniqueConstraint(source_lead_id, history_hash, analysis_version)` evita duplicados; sin `--force` se omiten los ya evaluados.
- **Progreso**: `AnalysisRun.heartbeat_at` + `AnalysisRunStep` alimentan el terminal; el polling del navegador los consume.
- **Cancelación**: `threading.Event` compartido (el dashboard lo activa); no mata procesos, solo corta el gasto de tokens.

---

## 12. Reglas y consideraciones

- **Solo Django ORM**; el CRM (`propifai`) se lee solo con SELECT y todo se persiste en la BD `default`.
- **Azure SQL** (mssql): nada de sintaxis PostgreSQL.
- **Costo**: el costo exacto por lead solo aplica a evaluaciones nuevas (las históricas no tienen `trace_id`).
- **Precios**: configurables por entorno `DEEPSEEK_PRICE_INPUT_PER_1M` / `DEEPSEEK_PRICE_OUTPUT_PER_1M` (default `0.14` / `0.28` USD por 1M tokens).
- **Calidad**: toda decisión "confirmada" exige evidencia (índices de mensajes del lead); la revisión humana mide acuerdo y errores (falsos positivos/negativos).
