# Bot Nocturno de Propiedades — Guía de conexión (WhatsApp / n8n)

Guía operativa del respondedor inicial de WhatsApp para propiedades. Cómo encontrarlo en el menú, dónde está el dashboard, los endpoints, la autenticación, el payload/respuesta y los pasos para conectarlo desde n8n.

---

## 1. Dónde está en el menú

- Entrada de menú: **"Bot nocturno"** (ícono 💬 WhatsApp) → definida en
  [`webapp/templates/base.html`](webapp/templates/base.html:1256).
- URL del dashboard: **`/intelligence/whatsapp-initial-responder/`**

## 2. Dashboard (panel de control)

| Ruta | Método | Descripción |
|---|---|---|
| `/intelligence/whatsapp-initial-responder/` | GET | Métricas (total, respondidos, ignorados, en revisión, errores, latencia media), estado del horario (`schedule`), últimas 100 interacciones. |
| `/intelligence/whatsapp-initial-responder/` | POST | Activar/desactivar bot (`enabled`) y configurar **ventana horaria** (`start_time`, `end_time`). Guarda auditoría (`PropertyBotControlAudit`). |
| `/intelligence/whatsapp-initial-responder/<uuid>/` | GET | Detalle de una interacción (evidencia, respuesta, revisión). |
| `/intelligence/whatsapp-initial-responder/<uuid>/review/` | POST | Revisión humana: `verdict = confirmed_ok | confirmed_error` + `note`. |

- Vista: [`property_bot_dashboard()`](webapp/n8n_bridge/property_bot_views.py:79).
- Acceso: niveles de gerencia (4–5).
- Configuración persistida en modelo `PropertyBotConfiguration` (tabla `n8n_property_bot_configuration`):
  - `enabled` (bool), `start_time` (default `00:00`), `end_time` (default `05:00`),
    `timezone_name` (default `America/Lima`),
    `require_external_conversation_id` (default `True`),
    `enabled_property_types` (default: casa, departamento, terreno, local_comercial).

## 3. Endpoints (API n8n)

Prefijo raíz: **`/api/n8n/`** (definido en [`webapp/urls.py`](webapp/urls.py:116)).

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/n8n/ping/` | Test de conexión (nodo de prueba en n8n). |
| POST | `/api/n8n/message/` | Puente de leads existente. |
| POST | `/api/n8n/reset/` | Reset de sesión de lead. |
| **POST** | **`/api/n8n/property-bot/v1/initial-response/`** | **El endpoint del bot nocturno** (vista [`initial_property_response()`](webapp/n8n_bridge/property_bot_views.py:37)). |

### 3.1 Autenticación
- Header: **`X-N8N-API-Key: <valor>`**
- El valor esperado se lee de la variable de entorno **`N8N_BRIDGE_API_KEY`**.
- Si no coincide → `401 {"success": false, "error": "API key inválida"}`.

### 3.2 Payload (JSON)
Campos que espera `process_initial_message`:

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `message_id` | string | Sí | ID único del mensaje (idempotencia). Puede ir también en header `X-Idempotency-Key`. |
| `phone` | string | Sí | Número de WhatsApp del cliente. |
| `text` | string | Sí | Texto del mensaje (máx 2000 caracteres). |
| `external_conversation_id` | string | Según config | ID del hilo/conversación en la plataforma (necesario si `require_external_conversation_id=True`, default). |
| `contact_name` | string | No | Nombre del contacto (se guarda en memoria episódica). |
| `human_takeover` | bool | No | `true` → el humano tomó el caso, el bot ignora (`HUMAN_TAKEOVER`). |

### 3.3 Respuesta (JSON)
```json
{
  "success": true,
  "action": "respond_once",
  "reply_text": "PROP000261 · Casa en Urb. Colonial II — 180 m² · 4 dorm. · US$ 223 000",
  "reason_code": "ANSWER_SENT",
  "interaction_id": "<uuid>",
  "property_code": "PROP000261",
  "bot_finished_for_conversation": true,
  "delivery_mode": "immediate",
  "delay_seconds": 0
}
```
- `action`: `respond_once` (enviar `reply_text`) o `ignore` (no enviar nada; `reply_text` vacío).
- `bot_finished_for_conversation`: cuando es `true`, el bot ya respondió este hilo y **no debe volver a responder** (lógica one-shot).
- Para captación, `delivery_mode` es `delayed`, `delay_seconds` indica la espera restante y `send_not_before` contiene la hora ISO exacta. En reintentos idempotentes la espera restante se recalcula, por lo que no vuelve a comenzar desde cero.

### 3.4 Reason codes (para depurar / decidir en n8n)
| reason_code | Significado | ¿reply? |
|---|---|---|
| `ANSWER_SENT` | Respondió la propiedad. | ✅ |
| `CAPTACION_SCHEDULED` | Captación aceptada; enviar en `send_not_before`. | ✅, con espera |
| `DUPLICATE_MESSAGE` | `message_id` repetido (idempotencia). | devuelve la respuesta anterior |
| `ALREADY_RESPONDED` | El hilo ya fue respondido antes. | ❌ |
| `HUMAN_TAKEOVER` | El humano tomó el caso. | ❌ |
| `BOT_DISABLED` | Bot apagado en configuración. | ❌ |
| `OUTSIDE_SCHEDULE` | Fuera de la ventana horaria (00:00–05:00 default). | ❌ |
| `MISSING_CONVERSATION_ID` | Falta `external_conversation_id`. | ❌ |
| `NO_PROPERTY_CODE` | El mensaje no menciona un código `PROPxxxx`. | ❌ |
| `MULTIPLE_PROPERTY_CODES` | Menciona más de una propiedad. | ❌ |
| `TITLE_CODE_MISMATCH` | El título no coincide con el código. | ❌ |
| `UNSUPPORTED_PROPERTY_TYPE` | Tipo no habilitado (ej. no casa/depa/terreno/local). | ❌ |
| `PROPERTY_NOT_PUBLISHABLE` | Vendida/pausada/no disponible. | ❌ |
| `VALIDATION_FAILED` / `MISSING_REQUIRED_DATA` | Faltan datos para armar la respuesta. | ❌ |
| `INTERNAL_ERROR` | Error inesperado (HTTP 500). | ❌ |

### 3.5 Códigos HTTP
- `200` con `success:true` (respondió o ignoró correctamente).
- `400`: campos requeridos faltantes o `text` > 2000.
- `401`: API key inválida.
- `500`: error interno (con `action:"ignore"`).

## 4. Flujo interno (para entender el comportamiento)
1. **Idempotencia** por `message_id` → si ya existe, devuelve la decisión previa.
2. **One-shot por hilo** (`external_conversation_id`): si el hilo ya recibió `respond_once`, ignora el resto.
3. **Guardas deterministas** en orden: `human_takeover` → `BOT_DISABLED` → `OUTSIDE_SCHEDULE` → `MISSING_CONVERSATION_ID` → `NO_PROPERTY_CODE` → `MULTIPLE_PROPERTY_CODES`.
4. Resolución del código con el agente [`AgenteRespuestaInicialWhatsApp`](webapp/intelligence/agents/respuesta_inicial_whatsapp_agent.py) (valida título, tipo habilitado, visibilidad, datos).
5. Render estricto con [`render_initial_response()`](webapp/n8n_bridge/services/initial_property_renderer.py:39) y guarda **memoria episódica** por teléfono.

## 5. Pasos para conectarlo desde n8n
1. **Crea el webhook de WhatsApp** (o nodo que reciba el mensaje del cliente) con: `message_id`, `phone`, `text`, `external_conversation_id` (id del hilo), `contact_name` (opcional).
2. **Nodo HTTP Request** hacia:
   - URL: `https://<TU_DOMINIO>/api/n8n/property-bot/v1/initial-response/`
   - Método: `POST`, Content-Type `application/json`.
   - Header: `X-N8N-API-Key: <N8N_BRIDGE_API_KEY>`.
   - Body (JSON): `{ "message_id": "{{$json.message_id}}", "phone": "{{$json.phone}}", "text": "{{$json.text}}", "external_conversation_id": "{{$json.external_conversation_id}}" }`.
3. **IF (n8n):** `$json.action === "respond_once"` → si `$json.delay_seconds > 0`, usar un nodo **Wait** hasta `send_not_before`.
4. Después del Wait, consultar nuevamente la conversación en WhatsApp/Chatwoot para saber si cualquier agente humano respondió.
5. Llamar `POST /api/n8n/property-bot/v1/confirm-captacion-delivery/` con `interaction_id` y `conversation_has_agent_reply` (boolean). Solo enviar el `reply_text` devuelto cuando `delivery_ready=true`. Si un agente respondió, la API devuelve `CAPTACION_CANCELLED_AGENT_REPLIED` y texto vacío.
   - `false` → no enviar nada (el agente humano atiende) o reenviar a un agente humano.
4. **Configura el horario** en el dashboard ("Bot nocturno") o vía `PropertyBotConfiguration`: default `enabled=false`, `00:00–05:00`, `America/Lima`. **El bot no responde hasta que `enabled=true`.**

## 6. Notas operativas
- El bot es **nocturno por defecto** (21:00–05:00 configurado en el dashboard; default 00:00–05:00). Fuera de ese rango responde `OUTSIDE_SCHEDULE`/ignora → el agente humano responde.
- **One-shot:** por cada hilo responde **una sola vez**; los mensajes posteriores del cliente se ignoran (evita spam nocturno).
- Solo responde si el mensaje contiene **un único código de propiedad** (`PROPxxxx`); si menciona el título sin código, se valida la consistencia pero el disparador principal es el código.
- Los `message_id` y `external_conversation_id` son claves: úsalos desde la plataforma de WhatsApp/n8n para que la idempotencia y el one-shot funcionen.

## 7. Emulador de pruebas (WhatsApp)
Entorno que replica **exactamente la lógica real** del endpoint, sin llamadas externas a n8n.

### Rutas
| Ruta | Método | Descripción |
|---|---|---|
| `/intelligence/whatsapp-initial-responder/emulador/` | GET | Mockup de celular WhatsApp con campos **Nombre** y **Número** del contacto. Vista [`property_bot_emulator()`](webapp/n8n_bridge/property_bot_views.py:159). |
| `/intelligence/whatsapp-initial-responder/emulador/api/reply/` | POST | Procesa el mensaje con la lógica real (form-urlencoded: `message`, `name`, `phone`). Vista [`property_bot_emulator_reply()`](webapp/n8n_bridge/property_bot_views.py:170). |

### Cómo funciona
- El emulador construye el payload real y llama a la **misma función** que usa el endpoint: [`process_initial_message(payload, ignore_schedule=True)`](webapp/n8n_bridge/services/initial_property_responder.py:56).
- `phone` se normaliza a E.164 Perú (móvil `9XXXXXXXX` → `519XXXXXXXX`). El thread de la conversación es `emulador:{dígitos}` → **el one-shot funciona**: tras la primera respuesta, los mensajes siguientes devuelven `ALREADY_RESPONDED` y el emulador guarda **silencio total** (igual que en producción).
- `ignore_schedule=True` solo salta la ventana horaria (para probar a cualquier hora). **Todo lo demás es 100% la lógica de producción.**
- **Persistencia:** cada mensaje crea un registro en `PropertyBotInitialResponse` (aparecen en "Interacciones recientes" del dashboard) y la primera respuesta guarda **memoria episódica** (lead + conversación + episodio `funnel_stage: waiting_for_human`).
- La columna "Hora" del dashboard usa la hora del computador (`TIME_ZONE='America/Lima'`, `USE_TZ=True` en [`settings.py`](webapp/settings.py:214)).
