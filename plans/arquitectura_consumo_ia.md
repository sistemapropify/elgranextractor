# Arquitectura y estructura del consumo de IA (Prometeo / Propifai)

> Objetivo: saber **qué proceso usa qué API de IA**, con qué modelo, desde qué archivo,
> y poder **trackear todo en el dashboard `/intelligence/consumo-ia/`**.
> Documento basado en el código real (septiembre 2026). Si algo no coincide con el código,
> manda el código.

---

## 1. Proveedores y modelos de IA en uso

| Proveedor | API / endpoint | Modelo | Para qué se usa | Costo |
|---|---|---|---|---|
| **DeepSeek** | `POST https://api.deepseek.com/chat/completions` | `deepseek-v4-flash` (`LLMService.DEEPSEEK_MODEL`) | Todo el texto/razonamiento: análisis de leads, respuestas, chat, skills, memoria, formateo, auditoría | $0.14 / 1M tokens entrada · $0.28 / 1M salida |
| **Alibaba DashScope** | `POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation` | `qwen-vl-max` | **Visión/OCR**: leer el texto de las fotos de captaciones (`prospects`) | por tokens (ver `usage` de la respuesta) |
| **Embeddings locales** | `intfloat/multilingual-e5-small` (384 dims) + FAISS | — | Búsqueda semántica, RAG, matching híbrido | **sin costo de API** (CPU local) |

Variables de entorno: `DEEPSEEK_API_KEY`, `DEEPSEEK_MAX_TOKENS`, `QWEN_API_KEY`.

---

## 2. El gateway único (99% del consumo)

Todo el tráfico de texto pasa por **un solo cliente**:

```
intelligence/services/llm.py  →  class LLMService
    ├── _call_deepseek_api(...)                 # única función que hace requests.post a DeepSeek
    ├── generate_response(...)                  # síncrono
    ├── generate_streaming_response(...)        # streaming (SSE)
    └── generate_rag_response(...)              # con contexto RAG
```

En cada llamada (éxito o error) se registra el consumo con:

```python
AIConsumptionLog.registrar_llamada(
    model_name=..., endpoint=..., caller_app=...,
    prompt_tokens=..., completion_tokens=..., duration_ms=..., success=..., status_code=...,
)
```

→ tabla `intelligence_ai_consumption_log` (modelo `AIConsumptionLog` en `intelligence/models.py`).
**Consecuencia:** instrumentar un proceso nuevo = llamarlo con `caller_app` y `endpoint` explícitos.

## 3. Cómo se identifica hoy el proceso (`caller_app`)

Dos mecanismos, en este orden:

1. **Explícito** (lo correcto): el llamador pasa `caller_app="..."` y `endpoint="..."`.
2. **Auto-detección por pila** si faltan (`llm.py`, líneas ~115-162), según la ruta del archivo:

| Ruta del frame | `caller_app` resultante |
|---|---|
| `intelligence/services/` | `intelligence.services` |
| `intelligence/skills/<fichero>` | `intelligence.skills.<función>` |
| `intelligence/views.py` | `intelligence.views` |
| `whatsapp_extractor/` | `whatsapp_extractor` |
| `ingestas/` | `ingestas` |
| `chat_processor` | `intelligence.chat_processor` |
| `episodic_memory` | `intelligence.episodic_memory` |
| `memory` | `intelligence.memory` |
| *(cualquier otra ruta)* | **`''` → aparece como `desconocido`** |

**Huecos de la auto-detección:** `lead_intelligence/`, `response_intelligence/`,
`requerimientos/`, `prospects/` y el orquestador de skills **no tienen regla**, por eso
el dashboard muestra `desconocido` y `intelligence.skills.execute` sin decir si fue
"análisis de leads" o "requerimientos".

---

## 4. Inventario de procesos que consumen IA

| # | Proceso (negocio) | Archivo / punto de entrada | API · Modelo | `caller_app` actual | Estado |
|---|---|---|---|---|---|
| 1 | **Análisis contextual de leads** | `lead_intelligence/contextual_analysis.py` | DeepSeek · flash | `desconocido` | ⚠️ sin etiquetar |
| 2 | **Análisis masivo de conversaciones** | `lead_intelligence/management/commands/analyze_lead_conversations.py` + skill `analizar_conversacion_lead` | DeepSeek · flash | `intelligence.skills.<fn>` | ⚠️ ambiguo |
| 3 | **Respondedor / borradores de respuesta** | `response_intelligence/services.py`, `shadow.py`, `management/commands/generate_draft_responses.py` | DeepSeek · flash | `desconocido` | ⚠️ sin etiquetar |
| 4 | **Extracción de WhatsApp (normalizar export)** | `whatsapp_extractor/services/deepseek_transformer.py` | DeepSeek · flash | `whatsapp_extractor` | ✅ |
| 5 | **Deduplicación IA de requerimientos** | `whatsapp_extractor/services/deduplicacion_ia.py` | DeepSeek · flash | `whatsapp_extractor` | ✅ (mezclado con #4) |
| 6 | **Asistente web / chat** | `intelligence/services/chat_processor.py` | DeepSeek · flash | `chat_processor` | ✅ |
| 7 | **Formateo de respuestas (skill y RAG)** | `intelligence/agents/formatter_agent.py` | DeepSeek · flash | `formatter_agent` | ✅ |
| 8 | **Juez semántico de ejecución** | `intelligence/agents/semantic_execution_judge.py` | DeepSeek · flash | `execution_judge` | ✅ |
| 9 | **Compilador semántico de intención** | `intelligence/reasoning/semantic_compiler.py` | DeepSeek · flash | `semantic_intent_compiler` | ✅ |
| 10 | **Auditoría de aprendizaje (PIL)** | `intelligence/learning/auditor.py` | DeepSeek · flash | `learning_auditor` | ✅ |
| 11 | **Skills de IA** (intención WhatsApp, contexto, etc.) | `intelligence/skills/*.py` | DeepSeek · flash | `intelligence.skills.<fn>` | ⚠️ 1 fila por función |
| 12 | **Memoria** (hechos y episódica) | `intelligence/services/memory.py`, `episodic_memory.py` | DeepSeek · flash | `intelligence.memory` / `…episodic_memory` | ✅ |
| 13 | **Embeddings / RAG / matching híbrido** | `intelligence/services/rag.py`, `intelligence/skills/matching_hybrid.py` | Local e5-small + FAISS | — | ⚪ sin costo API |
| 14 | **OCR de fotos de captaciones** | `prospects/views.py` → `ProcessImageView._call_qwen()` | **DashScope · `qwen-vl-max`** | — | ❌ **punto ciego total** |

---

## 5. Problemas detectados en el dashboard actual

1. La tabla principal usa el `caller_app` **crudo**: `intelligence.skills.execute` no dice
   nada y `desconocido` agrupa procesos distintos.
2. Las filas `desconocido` con todos los valores en 0 solo ocupan espacio.
3. La tabla **no muestra fecha y hora**, ni el módulo de negocio (leads vs. requerimientos).
4. El consumo de **Qwen-VL (OCR de fotos)** no se registra: no aparece en ningún lado.
5. No hay una vista que responda "**qué procesos usan API y qué API afecta a qué proceso**".

---

## 6. Diseño propuesto (lo que se implementa)

### 6.1 Registro canónico de procesos (backend, `intelligence/procesos_ia.py`)
Un solo diccionario que traduce cualquier `caller_app` a lenguaje de negocio:

```python
PROCESOS_IA = {
  'lead_intelligence':        {'modulo': 'Análisis de leads',            'proveedor': 'DeepSeek', 'modelo': 'deepseek-v4-flash', 'archivo': 'lead_intelligence/contextual_analysis.py'},
  'response_intelligence':    {'modulo': 'Respondedor de leads',         'proveedor': 'DeepSeek', ...},
  'whatsapp_extractor':       {'modulo': 'Extracción de WhatsApp',       'proveedor': 'DeepSeek', ...},
  'chat_processor':           {'modulo': 'Asistente web (chat)',         'proveedor': 'DeepSeek', ...},
  ...
  'prospects.qwen_vl':        {'modulo': 'OCR de fotos (captaciones)',   'proveedor': 'Alibaba DashScope', 'modelo': 'qwen-vl-max', 'archivo': 'prospects/views.py'},
}
```
+ `normalizar_proceso(caller_app, endpoint)` que agrupa variantes
(`intelligence.skills.execute` → "Orquestador de skills", `intelligence.services` → según endpoint, …).

### 6.2 Instrumentar el punto ciego
En `prospects/views.py` (`_call_qwen`) registrar el uso de Qwen-VL con
`AIConsumptionLog.registrar_llamada(caller_app='prospects.qwen_vl', model_name='qwen-vl-max', …)`
usando los tokens que devuelve DashScope (y coste estimado propio).

### 6.3 Dashboard `/intelligence/consumo-ia/`
- **Filtro por proceso** con nombres legibles y agrupados por módulo.
- **Desglose por proceso (negocio)** en lugar de por `caller_app` crudo: módulo · API/modelo · llamadas · tokens · costo · % éxito · **última llamada (fecha y hora)**.
- **Últimas llamadas** con columnas: **fecha y hora (hora Perú)**, **módulo**, proceso técnico, API/modelo, tokens y costo.
- **Mapa de procesos → API**: tabla con *todos* los procesos conocidos, su API/modelo, su archivo y su estado (**con actividad hoy / sin actividad hoy / sin instrumentar**), para ver de un golpe "qué API afecta a qué proceso".
- Se ocultan las filas todo-cero y el `desconocido` sin datos.

### 6.4 Fases siguientes (opcional, no en esta entrega)
1. Pasar `caller_app` explícito en `lead_intelligence`, `response_intelligence` y `requerimientos`
   (deja de depender de la pila).
2. Alertas de costo por proceso (umbral diario) y desglose por modelo.
3. Guardar el `trace_id` para cruzar consumo con el lead/proceso concreto.
