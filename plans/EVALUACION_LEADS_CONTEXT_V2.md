# Evaluación de Leads · context-v2

> Documento técnico que explica qué es **`context-v2`**, cómo se estructura la
> evaluación de leads, cómo se calculan las métricas de **confianza** y
> **pertinencia**, y cómo califica el sistema. Se basa directamente en el código
> (`lead_intelligence` + `intelligence`) y en la salida real de una evaluación.

---

## 1. ¿Qué es `context-v2`?

`context-v2` es el **identificador de versión del motor de análisis contextual de
conversaciones de leads**. Está definido en
[`lead_intelligence/contextual_analysis.py`](webapp/lead_intelligence/contextual_analysis.py:11):

```python
ANALYSIS_VERSION = "context-v2"
```

### Qué es exactamente
Es la **regla de negocio + el esquema de salida** que usa DeepSeek para leer una
conversación completa de un lead (lo que escribió el lead y lo que escribió el
agente) y producir un **veredicto estructurado y verificable**.

### Su función
1. **Clasificar** cada conversación en decisiones discretas (calificación,
   intención de visita, calidad de primera respuesta).
2. **Medir** la confianza de cada decisión y la calidad de la primera atención
   (pertinencia, cobertura, respuesta directa, personalización).
3. **Exigir evidencia**: cualquier decisión "positiva" debe apuntar a mensajes
   reales escritos por el lead (o por el agente, en el caso de la primera
   respuesta); si no hay evidencia válida, la decisión se degrada a `ambiguous`.
4. **Versionar** resultados: como el `analysis_version` se guarda en cada
   registro (`LeadConversationAssessment`), el sistema puede recalcular todo con
   una versión nueva sin mezclar resultados viejos, y el dashboard de "Calidad
   del motor IA" audita solo la versión vigente.

La cadena de análisis completa está en
[`analyze_conversation_context()`](webapp/lead_intelligence/contextual_analysis.py:117).

---

## 2. Estructura de la evaluación de leads (pipeline)

El pipeline tiene **4 etapas**. Solo la etapa 2 usa IA (DeepSeek); las demás son
determinísticas y baratas.

```
┌───────────────────────────────────────────────────────────────────────────┐
│  1. ANÁLISIS ESTRUCTURAL (determinístico, sin IA)                          │
│     conversation_analysis.analyze_chat_history(chat_history)              │
│     → mensajes válidos, remitentes (lead/agent), timestamps,              │
│       contactado, bidireccional, interés, intención, desatendido          │
└───────────────────────────────────┬───────────────────────────────────────┘
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  2. ANÁLISIS CONTEXTUAL (IA · DeepSeek)                                   │
│     AnalizarConversacionLeadSkill → analyze_conversation_context(...)     │
│     → qualified_status, visit_intent_status, first_response_status,       │
│       confianzas (0-1), pertinencia/cobertura/directa/personalización,    │
│       evidencia (índices de mensajes), solicitudes cubiertas/pendientes   │
└───────────────────────────────────┬───────────────────────────────────────┘
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  3. GUARDAS DETERMINÍSTICAS (sobrescriben al LLM si contradicen la        │
│     estructura):                                                          │
│     - sin bidireccional  → qualified_status = not_confirmed              │
│     - sin contacto       → first_response_status = not_applicable        │
│     - "confirmed" sin evidencia → ambiguous                               │
└───────────────────────────────────┬───────────────────────────────────────┘
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  4. PERSISTENCIA                                                          │
│     LeadConversationAssessment.update_or_create(                          │
│         source_lead_id + history_hash + analysis_version)                 │
│     Tabla: prometeo_lead_conversation_assessment                          │
└───────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Etapa 1 — Estructural (sin IA)
Función: [`analyze_chat_history()`](webapp/lead_intelligence/conversation_analysis.py:155).

- Normaliza el `chat_history` (JSON), descarta mensajes sin contenido útil o sin
  fecha válida, reconoce solo remitentes `lead`/`agent`, ordena por timestamp.
- Calcula indicadores determinísticos:
  - `contacted` / `first_agent_response_at` / `first_response_seconds`
  - `bidirectional` / `bidirectional_at`
  - `has_interest` / `interest_at` (patrones de interés: precio, ubicación, área,
    financiamiento, visita, etc. — ver `INTEREST_PATTERNS`)
  - `qualified` / `qualified_at`
  - `visit_intent` / `visit_intent_at` (patrones `VISIT_INTENT_PATTERNS`)
  - `unattended` (último mensaje del lead sin respuesta posterior del agente)

Esta etapa **no cuesta llamadas a la IA** y es la misma que alimenta el embudo
del dashboard gerencial.

### 2.2 Etapa 2 — Contextual (DeepSeek)
Función: [`analyze_conversation_context()`](webapp/lead_intelligence/contextual_analysis.py:117),
invocada por el skill `AnalizarConversacionLeadSkill` (registrado como
`analizar_conversacion_lead`).

- Construye un **transcript** con `message_index`, `sender`, `timestamp`, `text`.
- Envía a DeepSeek (vía `LLMService.extract_structured_data`) un JSON con:
  - **Instrucciones de negocio**: qué cuenta como "calificado", qué cuenta como
    "intención de visita" (no basta pedir ubicación/precio), cómo validar
    evidencia, cuándo usar `ambiguous`, cómo evaluar la primera atención y las
    solicitudes explícitas del bloque inicial.
  - **Esquema de salida** (los campos que DeepSeek debe devolver).
- Reintenta hasta **3 intentos** si la respuesta no es válida.
- **Valida la salida**:
  - `qualified_status == "confirmed"` **sin** evidencia de mensajes del lead → se
    degrada a `ambiguous`.
  - `visit_intent_status == "confirmed"` sin evidencia → `ambiguous`.
  - `first_response_status` en {adequate, partial, inadequate} sin evidencia de
    mensajes del agente → `ambiguous`.

### 2.3 Etapa 3 — Guardas determinísticas
Aplicadas por el comando
[`analyze_lead_conversations`](webapp/lead_intelligence/management/commands/analyze_lead_conversations.py:54)
después del LLM:

```python
if not structural["bidirectional"]:
    assessment["qualified_status"] = "not_confirmed"
    assessment["qualified_evidence"] = []
if not structural["contacted"]:
    assessment["first_response_status"] = "not_applicable"
    assessment["first_response_evidence"] = []
```

Es decir: si estructuralmente no hubo conversación bidireccional, la IA **no
puede** decir que el lead está calificado, y si el agente nunca respondió, la
"calidad de primera respuesta" es `not_applicable`.

### 2.4 Etapa 4 — Persistencia
Modelo [`LeadConversationAssessment`](webapp/lead_intelligence/models.py:142),
tabla `prometeo_lead_conversation_assessment`, con constraint único
`(source_lead_id, history_hash, analysis_version)`.

El **`history_hash`** (SHA-256 del `chat_history`, ver
[`conversation_hash()`](webapp/lead_intelligence/contextual_analysis.py:22)) es
la clave de **incrementalidad**: si la conversación no cambió y ya hay una
evaluación con la misma versión, **no se vuelve a llamar a DeepSeek** (a menos
que uses `--force`).

### 2.5 Disparo
- **Manual por consola**: `py manage.py analyze_lead_conversations --from YYYY-MM-DD --to YYYY-MM-DD` (o `--lead-id N`).
- **Desde el dashboard** "Calidad del motor IA" (`/analisis-crm/calidad-motor/`):
  botón **"▶ Ejecutar evaluación IA"** (vista
  [`run_analysis()`](webapp/lead_intelligence/views.py:225)).

---

## 3. Cómo califica el sistema (métricas y escalas)

### 3.1 Decisiones discretas (escalas cerradas)

**Calificación comercial** (`qualified_status`):
| Valor | Significado |
|---|---|
| `confirmed` | El lead muestra **interés comercial concreto** (pregunta/negocia una propiedad real), respaldado por evidencia. |
| `not_confirmed` | No hay interés concreto confirmado (o la conversación no es bidireccional). |
| `ambiguous` | La evidencia no permite afirmar ni negar. |

**Intención de visita** (`visit_intent_status`):
| Valor | Significado |
|---|---|
| `confirmed` | El lead **pide/propone visitar**, acepta claramente una propuesta del agente, ofrece disponibilidad o acuerda fecha/hora. |
| `not_confirmed` | Sin intención real de visita. |
| `ambiguous` | Evidencia insuficiente. |

> Regla clave: pedir **ubicación, precio o características NO es intención de
> visita**, y una propuesta **solo del agente** no cuenta.

**Calidad de la primera respuesta** (`first_response_status`):
| Valor | Significado |
|---|---|
| `adequate` | Responde pertinente y **suficientemente** lo pedido. |
| `partial` | Responde solo una parte de lo solicitado. |
| `inadequate` | Ignora, evade o contradice la solicitud. |
| `not_applicable` | No existe solicitud evaluable o no hubo respuesta del agente. |
| `ambiguous` | Evidencia insuficiente. |

### 3.2 Confianza (0–1)
- `qualified_confidence`
- `visit_intent_confidence`
- `first_response_confidence`

**Qué es**: la confianza del modelo en que **su decisión** es correcta (no una
probabilidad de que el lead compre). Un `not_confirmed` con alta confianza (p. ej.
0.90) es tan válido como un `confirmed` con alta confianza.

**Cómo se normaliza**: [`_confidence()`](webapp/lead_intelligence/contextual_analysis.py:30)
recorta el valor a `[0, 1]` (cualquier no numérico → `0.0`).

**Cómo se usa en el dashboard**: el panel "Calidad del motor IA" considera
**baja confianza** a las decisiones con confianza `< 0.75` y las manda a la cola
de revisión humana, junto con las `ambiguous` y las que no tienen evidencia.

### 3.3 Puntajes de pertinencia (0–1)
Puntajes opcionales de la **calidad de la primera respuesta** (`None` si no
aplica):

| Métrica | Campo | Qué mide |
|---|---|---|
| **Pertinencia** | `relevance_score` | Si el agente habla de **lo que se pidió** (no se desvía a otro tema). |
| **Cobertura** | `coverage_score` | **Qué proporción** de las solicitudes concretas del lead responde el primer bloque. |
| **Respuesta directa** | `directness_score` | Si responde **sin evadir** ni desviar la conversación. |
| **Personalización** | `personalization_score` | Si adapta la respuesta a las **necesidades expresadas** (no basta usar el nombre). |

Definición exacta en las instrucciones a DeepSeek (campo `attention_scores` de
[`contextual_analysis.py`](webapp/lead_intelligence/contextual_analysis.py:163)).

### 3.4 Reglas de evidencia (lo que "ancla" cada decisión)
- `qualified_evidence`: índices de mensajes **escritos por el lead** que prueban
  la calificación.
- `visit_intent_evidence`: índices de mensajes **escritos por el lead** que
  demuestran intención real de visita.
- `first_response_evidence`: índices del **primer bloque consecutivo del agente**
  (ver [`_first_response_agent_indices()`](webapp/lead_intelligence/contextual_analysis.py:99)).

La validación de índices está en
[`_validated_evidence()`](webapp/lead_intelligence/contextual_analysis.py:67):
descarta índices fuera de rango, remitentes incorrectos o no permitidos.

---

## 4. Ejemplo real (de tu sistema)

> Evaluación contextual IA
> **Calificación: No confirmado (0,35) · Intención de visita: No confirmado (0,90).**
> El lead pide "más información" sobre un terreno, lo que muestra interés
> comercial pero no un compromiso concreto de compra ni intención de visitar. El
> agente responde con ubicación, área y precio, y pregunta si es para vivienda o
> proyecto.
>
> **Calidad de la primera respuesta: Adecuada · confianza 85%**
> Pertinencia 90% · cobertura 80% · respuesta directa 90% · personalización 60%.
> El agente responde directamente a la solicitud genérica proporcionando
> características clave del terreno y pregunta para precisar la necesidad.

Análisis de esta salida con la lógica de `context-v2`:
- El **bloque inicial** del lead es genérico ("más información"): la regla
  `explicit_request_rule` evita inventar que pidió precio/ubicación/área; por
  eso no es `confirmed` (confianza 0.35) pero tampoco `not_confirmed` rotundo.
- La **intención de visita** se mantiene `not_confirmed` con confianza alta
  (0.90): pedir información **no** cuenta como intención de visitar.
- La **primera respuesta** es `adequate`: responde lo que se pidió (características
  clave del terreno), añade una pregunta razonable para precisar la necesidad, y
  no se penaliza que sea una plantilla (la regla `attention_quality` solo
  penaliza si es genérica, evade, contradice o deja solicitudes sin responder).
  Por eso pertinencia 0.90 y cobertura 0.80; la personalización (0.60) baja
  porque la respuesta es en parte estándar.

---

## 5. Modelo de datos (resumen)

Tabla `prometeo_lead_conversation_assessment` — modelo
[`LeadConversationAssessment`](webapp/lead_intelligence/models.py:142):

| Campo | Tipo | Uso |
|---|---|---|
| `source_lead_id` | BIGINT | Lead del CRM evaluado |
| `history_hash` | CHAR(64) | Hash SHA-256 del `chat_history` (incrementalidad) |
| `analysis_version` | CHAR(40) | `context-v2` (versión vigente) |
| `qualified_status` / `qualified_confidence` | CHAR / DECIMAL | Calificación + confianza |
| `visit_intent_status` / `visit_intent_confidence` | CHAR / DECIMAL | Intención de visita + confianza |
| `qualified_evidence` / `visit_intent_evidence` | JSON | Evidencia (mensajes del lead) |
| `reason` | TEXT | Explicación que contrasta lead vs. propuestas del agente |
| `first_response_status` / `first_response_confidence` | CHAR / DECIMAL | Calidad 1.ª respuesta + confianza |
| `relevance_score` / `coverage_score` / `directness_score` / `personalization_score` | DECIMAL | Puntajes 0–1 de pertinencia |
| `lead_request_items` / `answered_request_items` / `unanswered_request_items` | JSON | Solicitudes explícitas y su cobertura |
| `first_response_evidence` | JSON | Primer bloque del agente |
| `attention_reason` | TEXT | Justificación de la calidad de atención |
| `model_version` | CHAR(80) | Modelo DeepSeek usado |
| `analyzed_at` | DATETIME | Cuándo se evaluó |

---

## 6. ¿Por qué un lead corto cuesta igual o parecido?

Tu pregunta: *"¿por qué el costo es caro si un lead es así de corto?"*

La respuesta está en **cómo se cobra** DeepSeek (por **tokens**, no por número de
mensajes):

1. **El prompt es grande y fijo.** Cada evaluación envía a DeepSeek las
   instrucciones completas de negocio + el esquema de salida (`context-v2`) +
   el transcript. Las instrucciones y el esquema son **cientos de tokens** que se
   cobran en **cada** llamada, estén vacíos o llenos.
2. **La salida también es grande.** DeepSeek devuelve un JSON estructurado con
   razón, evidencia, solicitudes, puntajes, etc. En tus logs cada respuesta
   consume ~**3 200–3 400 tokens** y tarda ~15–20 s, aunque la conversación tenga
   1 mensaje del lead y 1 del agente.
3. **Es por lead.** La evaluación es **individual** (1 llamada por lead), no en
   lote; con 4 workers en paralelo, 619 leads implican ~619 llamadas.
4. **Reintentos.** Si una respuesta no valida el esquema, se reenvía hasta 3
   veces (más costo).

**Cómo se controla el costo:**
- **Incrementalidad por hash**: si el `chat_history` del lead no cambió y ya hay
  una evaluación `context-v2`, **no se vuelve a llamar** a DeepSeek (opción por
  defecto). Usa "Recalcular los ya evaluados" (`--force`) solo cuando cambiaste
  las reglas o el modelo.
- **Periodo acotado**: elige rangos de fecha pequeños desde el dashboard.
- El costo es dominado por el **prompt fijo**, no por la longitud de la
  conversación: acortar conversaciones no reduce el costo por lead.

---

## 7. Instrucciones de negocio actuales (texto literal del código)

El contenido siguiente es el dict `instructions` que se envía a DeepSeek en
[`analyze_conversation_context()`](webapp/lead_intelligence/contextual_analysis.py:127),
junto con el esquema de salida y las guardas determinísticas. Es la **regla de
negocio vigente** de `context-v2`.

### 7.1 Instrucciones principales (campo por campo)

- **`task`**: "Evalúa la conversación completa, incluyendo quién propone,
  respuestas, condiciones, rechazos y cambios posteriores."

- **`qualified`**: "Confirmado solo si el lead muestra interés comercial
  concreto. Una respuesta social aislada no basta."

- **`visit_intent`**: "Confirmado solo si el lead solicita/propone visitar,
  acepta claramente una propuesta del agente, ofrece disponibilidad o acuerda
  fecha/hora. Pedir ubicación, precio o características no basta. Una propuesta
  exclusiva del agente no es intención del lead."

- **`evidence`**: "Devuelve únicamente índices de mensajes escritos por el lead
  que prueban cada decisión."

- **`uncertainty`**: "Si la evidencia no permite afirmar la decisión, usa
  `ambiguous` o `not_confirmed`; nunca supongas."

- **`attention_quality`**: "Evalúa también la primera atención. La solicitud
  inicial comprende todos los mensajes consecutivos del lead anteriores a la
  primera respuesta. La primera respuesta comprende todos los mensajes
  consecutivos del agente hasta que el lead vuelve a escribir. Determina si
  responde directa y completamente lo pedido. No penalices una plantilla por
  repetirse: penaliza solamente si es genérica, evade, contradice o deja
  solicitudes sin responder."

- **`explicit_request_rule`**: "Extrae únicamente solicitudes o preguntas
  expresadas de forma explícita por el lead en su bloque inicial. Frases
  genéricas como 'más info', 'información' o el mensaje automático de un anuncio
  NO autorizan a inventar que pidió precio, ubicación, área, financiamiento ni
  características. Si la petición es genérica, una respuesta pertinente que
  aporte información del inmueble o haga una pregunta razonable para precisar la
  necesidad puede ser adecuada; evalúa lo que realmente se escribió."

- **`first_response_scope`**: "`answered_request_items` y
  `unanswered_request_items` describen solo la cobertura del PRIMER bloque de
  respuesta. Mensajes posteriores pueden resolver esas dudas, pero no cambian
  retroactivamente la calidad de la primera respuesta. No presentes esas
  omisiones como solicitudes pendientes al cierre de toda la conversación."

- **`attention_scores`**: "`relevance` mide si habla de lo solicitado;
  `coverage` qué proporción de solicitudes concretas responde; `directness` si
  responde sin desviar la conversación; `personalization` si adapta la respuesta
  a las necesidades expresadas, no solo si usa el nombre."

- **`conversation`**: el transcript completo (message_index, sender, timestamp,
  text).

### 7.2 Esquema de salida (contrato con DeepSeek)

- `qualified_status`: uno de `confirmed`, `not_confirmed`, `ambiguous`.
- `qualified_confidence`: confianza en que `qualified_status` es correcto, 0–1
  ("también debe ser alta cuando `not_confirmed` está claramente sustentado").
- `qualified_evidence_indices`: `message_index` escritos por el lead que
  sustentan la calificación.
- `visit_intent_status`: `confirmed` / `not_confirmed` / `ambiguous`.
- `visit_intent_confidence`: 0–1; "no es probabilidad positiva: si claramente no
  hay intención, usa `not_confirmed` con confianza alta".
- `visit_intent_evidence_indices`: mensajes del lead que demuestran intención
  real de visita.
- `reason`: explicación breve que contraste lo dicho por el lead con las
  propuestas del agente.
- `first_response_status`: `adequate` / `partial` / `inadequate` /
  `not_applicable` / `ambiguous` ("Adequate exige respuesta pertinente y
  suficiente; partial responde solo una parte; inadequate ignora, evade o
  contradice; not_applicable si no existe solicitud evaluable o respuesta").
- `first_response_confidence`: 0–1.
- `relevance_score`, `coverage_score`, `directness_score`,
  `personalization_score`: puntuaciones 0–1.
- `lead_request_items`: "solo solicitudes explícitas del bloque inicial del
  lead; no descompongas 'más info' en detalles que no mencionó".
- `answered_request_items` / `unanswered_request_items`: solicitudes iniciales
  cubiertas / no cubiertas suficientemente por el primer bloque del agente.
- `first_response_agent_indices`: índices del primer bloque de respuesta del
  agente.
- `attention_reason`: explicación breve y verificable de la calidad de la
  primera respuesta.

### 7.3 Guardas determinísticas post-LLM (comando `analyze_lead_conversations`)

Aplicadas después de DeepSeek, **sobrescriben** al modelo si contradicen la
estructura:

1. `if not structural["bidirectional"]` → `qualified_status = "not_confirmed"` y
   `qualified_evidence = []`.
2. `if not structural["contacted"]` → `first_response_status = "not_applicable"`
   y `first_response_evidence = []`.
3. `if qualified_status == "confirmed" and not qualified_evidence` →
   `qualified_status = "ambiguous"`.
4. `if visit_status == "confirmed" and not visit_evidence` → `ambiguous`.
5. `if first_response_status in {adequate, partial, inadequate} and not
   first_response_evidence` → `ambiguous`.

### 7.4 Reglas estructurales determinísticas (sin IA)

En [`conversation_analysis.py`](webapp/lead_intelligence/conversation_analysis.py:16):

- **Interés comercial** (`INTEREST_PATTERNS`): "me interesa", precio/costo,
  ubicación/dirección/mapa, fotos/videos, área/metros/m²/características,
  disponibilidad, financiamiento/crédito/cuota/inicial, documentos/título,
  comprar/vivienda/proyecto, negociar/separar/reservar, visitar/visita/agendar.
- **Negación** (`NEGATIVE_INTEREST_PATTERNS`): "no me interesa", número/contacto
  equivocado, "se equivocó" (anulan el interés).
- **Intención de visita** (`VISIT_INTENT_PATTERNS`): quiero/quisiera/podemos…
  visitar/ver/conocer/agendar; "cuándo/que día/que hora… puedo… visitar".
- **Aceptación de propuesta** (`AFFIRMATIVE_PATTERNS`): sí, claro, ok, de
  acuerdo, perfecto, correcto, me parece.

---

## 8. Referencias de código

| Pieza | Archivo |
|---|---|
| Versión y motor contextual (`context-v2`) | [`lead_intelligence/contextual_analysis.py`](webapp/lead_intelligence/contextual_analysis.py:11) |
| Análisis estructural determinístico | [`lead_intelligence/conversation_analysis.py`](webapp/lead_intelligence/conversation_analysis.py:155) |
| Skill que orquesta la evaluación | `intelligence/skills/analizar_conversacion_lead.py` |
| Modelo de resultados | [`lead_intelligence/models.py`](webapp/lead_intelligence/models.py:142) |
| Comando de análisis (incremental) | [`lead_intelligence/management/commands/analyze_lead_conversations.py`](webapp/lead_intelligence/management/commands/analyze_lead_conversations.py:21) |
| Botón y vista de ejecución | [`lead_intelligence/views.py`](webapp/lead_intelligence/views.py:225) |
| Dashboard "Calidad del motor IA" | [`lead_intelligence/services.py`](webapp/lead_intelligence/services.py:1038) |
