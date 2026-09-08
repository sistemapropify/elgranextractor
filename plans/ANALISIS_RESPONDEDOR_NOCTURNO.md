# Análisis del Respondedor Nocturno

> Documento técnico que desglosa la estructura, arquitectura, flujo de datos y funciones del **respondedor nocturno** del sistema Prometeo. Generado como referencia de arquitectura y mantenimiento.

---

## 1. ¿Qué es el respondedor nocturno?

Es un **orquestador determinista de una sola respuesta (one-shot)** que atiende el **primer contacto de WhatsApp fuera del horario laboral** (por defecto `00:00–05:00`, zona `America/Lima`). Cuando un cliente escribe por primera vez un mensaje con un código de propiedad, el bot responde **una única vez** con una plantilla aprobada que incluye datos verificados de la propiedad, y deja claro que un asesor humano continuará la conversación en horario de atención.

No usa IA para redactar la respuesta de producción: todo es **determinista** (SELECT al CRM → plantilla). La IA solo interviene en un **modo "shadow"** opcional que genera un borrador en paralelo para auditar calidad, sin enviar nada.

- **Dominio:** `webapp/n8n_bridge`
- **Motivación declarada en código:** resolver el primer contacto nocturno de forma idempotente, auditable y sin costo de LLM.

---

## 2. Arquitectura general

```
                     ┌──────────────────────────────────────────────────┐
                     │                   n8n (WhatsApp)                 │
                     │        Webhook -> POST property-bot/v1/          │
                     └───────────────┬──────────────────────────────────┘
                                     │  X-N8N-API-Key
                                     ▼
                ┌────────────────────────────────────────────┐
                │   webapp/n8n_bridge/property_bot_views.py  │  Capa API
                │   initial_property_response()              │  (validate + auth)
                └───────────────┬────────────────────────────┘
                                ▼
                ┌────────────────────────────────────────────┐
                │  webapp/n8n_bridge/services/               │  Capa de servicios
                │  initial_property_responder.py            │  (procesador one-shot)
                │   -> process_initial_message(payload)     │
                └───┬──────────┬──────────┬──────────┬───────┘
                    ▼          ▼          ▼          ▼
        ┌──────────────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐
        │ detector     │ │ skill   │ │ renderer │ │ validator    │
        │ extraer      │ │ PROP000 │ │ plantilla│ │ guardrails   │
        │ código       │ │ SELECT  │ │ literal  │ │ deterministas│
        └──────────────┘ └─────────┘ └──────────┘ └──────────────┘
                    │                                        │
                    ▼                                        ▼
        ┌─────────────────────────────┐        ┌──────────────────────────┐
        │  Persistencia               │        │  Memoria episódica       │
        │  PropertyBotInitialResponse │        │  save_initial_episode()  │
        │  (DB default)               │        │  (intelligence)          │
        └─────────────────────────────┘        └──────────────────────────┘
                                │
                                ▼  (opcional, RESPONSE_INTELLIGENCE_SHADOW=1)
                ┌────────────────────────────────────────────┐
                │  webapp/response_intelligence/shadow.py    │
                │  spawn_shadow_draft() -> hilo daemon       │
                │  genera BotResponseDraft (shadow_live)     │
                └────────────────────────────────────────────┘
```

---

## 3. Estructura de archivos

### 3.1 Aplicación principal: `webapp/n8n_bridge`

| Ruta | Responsabilidad |
|------|-----------------|
| `models.py` | Persistencia: `PropertyBotConfiguration`, `PropertyBotInitialResponse`, `PropertyBotControlAudit` |
| `property_bot_views.py` | API externa del bot + dashboard de control, emulador y revisión humana |
| `views.py` | Puente general n8n↔ChatProcessor (chat libre por WhatsApp, no el bot nocturno) |
| `urls.py` | Rutas API (`/api/n8n/...`) |
| `dashboard_urls.py` | Rutas del dashboard del bot (`property-bot-dashboard`) |
| `apps.py` | Configuración de la app (`PropertyBotConfig`) |
| `migrations/` | Migraciones de `n8n_property_bot_configuration`, `n8n_property_bot_initial_response`, `n8n_property_bot_control_audit` |
| `services/initial_property_responder.py` | **Orquestador one-shot** (`process_initial_message`) |
| `services/initial_property_config.py` | Config efectiva + **guardia horaria** (`schedule_state`) |
| `services/initial_property_detector.py` | Detección determinista del código de propiedad |
| `services/initial_property_renderer.py` | Plantillas literales aprobadas + formateadores |
| `services/initial_property_validator.py` | Guardrails deterministas del payload y de la respuesta renderizada |
| `services/initial_property_memory.py` | Escritura de memoria episódica del lead |
| `tests/test_initial_property_bot.py` | Tests de detector, renderer, guardia horaria y contrato del endpoint |
| `templates/n8n_bridge/initial_responder/` | `dashboard.html`, `detail.html`, `emulator.html` |
| `static/n8n_bridge/initial_responder.css` | Estilos del emulador/dashboard |

### 3.2 Dependencias del motor de inteligencia

| Ruta | Responsabilidad |
|------|-----------------|
| `webapp/intelligence/agents/respuesta_inicial_whatsapp_agent.py` | Agente determinista (`AgenteRespuestaInicialWhatsApp`) que delega en el skill |
| `webapp/intelligence/skills/propiedades/informacion_inicial_propiedad.py` | **Skill** `InformacionInicialPropiedadSkill`: SELECT real al CRM (`propifai`) de datos verificados de la propiedad |
| `webapp/intelligence/agents/base_agent.py` | Contrato `BaseAgent` (el agente del bot sobrescribe `resolve` para one-shot) |
| `webapp/intelligence/services/chat_processor.py` | `ChatProcessor` (usado por memoria episódica y puente de chat) |
| `webapp/intelligence/services/episodic_memory.py` | `EpisodicMemoryService.save_episode` (memoria del lead) |

### 3.3 Motor IA en modo shadow (auditoría, no producción)

| Ruta | Responsabilidad |
|------|-----------------|
| `webapp/response_intelligence/shadow.py` | Genera `BotResponseDraft(mode='shadow_live')` en hilo daemon |
| `webapp/response_intelligence/prompt_assembly.py` | Ensambla prompt (few-shot + reglas de negocio + datos de propiedad en vivo) |
| `webapp/response_intelligence/curation.py` | `CurationService` (detección de categoría, curado de ejemplos) |
| `webapp/response_intelligence/guardrails.py` | Validación post-generación (alucinaciones, descuento, escalamiento) |
| `webapp/response_intelligence/models.py` | `BotResponseDraft`, `BotResponseEvaluation`, `CuratedExample`, `BusinessRule`, `MotorAIControl` |
| `webapp/response_intelligence/views.py` | Dashboard de calidad del motor IA (revisión, promoción a few-shot, switch shadow) |

---

## 4. Capa de datos (modelos)

### 4.1 `PropertyBotConfiguration` → tabla `n8n_property_bot_configuration`
Configuración operacional **singleton** (`singleton_key=1`).
- `enabled` (bool, default `False`)
- `start_time` / `end_time` (`TimeField`, default `00:00`–`05:00`)
- `timezone_name` (default `America/Lima`)
- `require_external_conversation_id` (default `True`)
- `enabled_property_types` (JSON, default `["casa","departamento","terreno","local_comercial"]`)
- `message_templates` (JSON, plantillas editables por tipo)
- `updated_at`, `updated_by` (auditoría)

### 4.2 `PropertyBotInitialResponse` → tabla `n8n_property_bot_initial_response`
**Decisión idempotente y auditable** para el primer mensaje de un hilo. Es la base de datos de evidencia de todo lo que el bot hace o no hace.
- Campos de evento: `message_id` (único), `external_conversation_id`, `conversation_property_key` (único), `received_at`, `latency_ms`.
- Privateidad: `phone_hash` (HMAC-SHA256 + `SECRET_KEY`), `phone_last4`, `phone`, `contact_name`.
- Propiedad: `property_id`, `property_code`, `property_type`.
- Mensajes: `incoming_text`, `response_text`.
- Decisión: `action` (`respond_once` | `ignore`), `reason_code`, `evidence` (JSON), `bot_enabled`, `schedule_snapshot`.
- Supervisión: `review_status` (`not_required`/`pending`/`confirmed_ok`/`confirmed_error`), `review_note`, `reviewed_at`, `reviewed_by`, `episode_id`, `error_type`, `error_preview`.

### 4.3 `PropertyBotControlAudit` → tabla `n8n_property_bot_control_audit`
Historial de cambios operacionales del bot (`configuration_update`, `templates_update`) con actor e IP.

---

## 5. Flujo del procesamiento (`process_initial_message`)

Código: `webapp/n8n_bridge/services/initial_property_responder.py:72`

1. **Idempotencia por mensaje** (`message_id`): si ya existe → devuelve registro con `DUPLICATE_MESSAGE`.
2. **Shadow live** (opcional): si `text` presente, lanza `spawn_shadow_draft` en hilo daemon (no bloquea).
3. **Hashing de teléfono**: `phone_digest()` normaliza y calcula digest HMAC.
4. **Config y guardia horaria**: `get_bot_configuration()` + `schedule_state(config)`.
5. **Thread estable**: `external_id` o fallback `phone:{digest}:{fecha}`.
6. **Guardias de silencio** (registran `action='ignore'` y un `reason_code`):
   - `ALREADY_RESPONDED` → ya hubo `respond_once` en el hilo (one-shot).
   - `HUMAN_TAKEOVER` → el humano tomó la conversación.
   - `BOT_DISABLED` → `config.enabled=False`.
   - `OUTSIDE_SCHEDULE` → fuera de la ventana nocturna.
   - `MISSING_CONVERSATION_ID` → falta id externo si se requiere.
7. **Detección del código** (`extract_property_identity`):
   - `NO_PROPERTY_CODE`, `MULTIPLE_PROPERTY_CODES`.
   - Coherencia de título con `title_is_consistent` → `TITLE_CODE_MISMATCH`.
8. **Resolución de datos** (`AgenteRespuestaInicialWhatsApp().resolve(code)` → `InformacionInicialPropiedadSkill().execute`):
   - Mapea `reason_code` de fallo → `PROPERTY_NOT_FOUND`, `UNSUPPORTED_PROPERTY_TYPE`, `INTERNAL_ERROR`, etc.
9. **Guardias sobre los datos**:
   - `UNSUPPORTED_PROPERTY_TYPE` (no está en `enabled_property_types`).
   - `PROPERTY_NOT_PUBLISHABLE` (invisible o estado en `{"vendida","vendido","pausada","pausado","no disponible"}`).
   - `MISSING_REQUIRED_DATA` / `VALIDATION_FAILED` (vía `validate_property_payload`).
10. **Render**: `render_initial_response(data, config)` arma la plantilla.
11. **Validación del render** (`validate_rendered_response`): contiene el saludo exacto, la ubicación y la frase de "asesor disponible".
12. **Persistencia atómica** (`transaction.atomic`): crea `PropertyBotInitialResponse(action='respond_once', reason_code='ANSWER_SENT', review_status='pending')`.
13. **Memoria episódica**: `save_initial_episode(...)` guarda el episodio y vincula `episode_id`.
14. **Respuesta**: devuelve el contrato one-shot `{success, action, reply_text, reason_code, interaction_id, property_code, bot_finished_for_conversation}`.

---

## 6. Contrato del endpoint (`initial_property_response`)

- **Método:** `POST /api/n8n/property-bot/v1/initial-response/`
- **Auth:** Header `X-N8N-API-Key` == env `N8N_BRIDGE_API_KEY` (comparación constante de tiempo con `hmac.compare_digest`).
- **Body requerido:** `message_id`, `phone`, `text` (max 2000 chars).
- **Opcionales:** `external_conversation_id`, `contact_name`, `human_takeover`.
- **Idempotencia:** si `message_id` vacío usa header `X-Idempotency-Key`.

### Respuesta de éxito (respondió)
```json
{
  "success": true,
  "action": "respond_once",
  "reply_text": "¡Gracias por escribirnos! 😊 ...",
  "reason_code": "ANSWER_SENT",
  "interaction_id": "<uuid>",
  "property_code": "PROP000261",
  "bot_finished_for_conversation": true
}
```

### Respuesta de ignorar (silencio)
```json
{
  "success": true,
  "action": "ignore",
  "reply_text": "",
  "reason_code": "ALREADY_RESPONDED"  // u otro
}
```

---

## 7. La skill: `InformacionInicialPropiedadSkill`

Código: `webapp/intelligence/skills/propiedades/informacion_inicial_propiedad.py`

- **Valida** el código con regex `PROP\d{6,9}`.
- **Ejecuta un SELECT** a la BD del CRM (`connections["propifai"]`) sobre `property`, `property_specs`, `property_type`, `currency`, `district`, `urbanization`, `property_status`.
- **Normaliza** tipo de propiedad y moneda (alias: "depa"→departamento, "soles"→PEN, etc.).
- Devuelve datos limpios:
  ```json
  {
    "property_id": 123,
    "code": "PROP000261",
    "title": "...",
    "property_type": "departamento",
    "location": "Urb. Colonial II, Paucarpata",
    "price": {"amount": 299000, "currency": "USD", "source": "..."},
    "features": [{"field":"bedrooms","value":3,"source":"property_specs.bedrooms"}, ...],
    "is_visible": true,
    "property_status": "Disponible"
  }
  ```
- Indica `reason_code` en caso de fallo: `NO_PROPERTY_CODE`, `PROPERTY_NOT_FOUND` (incluye códigos duplicados), `UNSUPPORTED_PROPERTY_TYPE`, `INTERNAL_ERROR`.

---

## 8. Plantillas y renderer

Código: `webapp/n8n_bridge/services/initial_property_renderer.py`

Plantillas por tipo (editables desde dashboard vía `message_templates`):
- `casa`, `departamento`, `local_comercial`: usan `{location}`, `{features}`, `{price}`.
- `terreno`: usa `{location}`, `{area}`, `{price}`.

Formateadores:
- `format_number`: miles separados con coma, sin decimales para enteros.
- `format_price`: `US$` si USD, `S/` si PEN.
- `format_feature`: dormitorios/baños/estacionamientos en singular/plural, áreas en `m²`.
- Máximo 2 características mostradas; para terreno solo `land_area`.

---

## 9. Guardrails deterministas (`initial_property_validator.py`)

- **Por tipo** se permiten solo ciertos campos (`ALLOWED_FIELDS`).
- `validate_property_payload`:
  - Tipo en plantillas soportadas.
  - `location` y `price` presentes.
  - 1–2 características, dentro del conjunto permitido.
  - Terreno debe empezar por `land_area`.
  - Moneda ∈ {`USD`, `PEN`}.
- `validate_rendered_response` (post-render): verifica saludo exacto, ubicación presente y la frase "Apenas uno de nuestros asesores esté disponible".

---

## 10. Guardia horaria (`schedule_state`)

Código: `webapp/n8n_bridge/services/initial_property_config.py:40`

- Convierte la hora actual a `timezone_name`.
- Ventana **start-inclusive, end-exclusive**:
  - Si `start < end` → dentro si `start <= now < end`.
  - Si `start > end` (cruza medianoche) → dentro si `now >= start` o `now < end`.
  - Si iguales → siempre dentro.
- Devuelve `{inside, local_now, timezone, start, end}` (se persiste como snapshot).

> Test: `ScheduleGuardTests` comprueba que `00:00` es dentro (`True`) y `05:00` fuera (`False`) para la ventana por defecto.

---

## 11. Modo shadow / motor IA (auditoría)

Código: `webapp/response_intelligence/shadow.py`

- Activado por `MotorAIControl.shadow_live_enabled` (switch persistente) o env `RESPONSE_INTELLIGENCE_SHADOW=1`.
- Solo genera un **borrador** (`BotResponseDraft(mode='shadow_live')`) en un **hilo daemon**; **nunca envía** a WhatsApp ni altera la respuesta determinista.
- **Guardrail de escalamiento** (spec §7): si el mensaje es de riesgo legal/escalamiento, NO genera con IA; registra `auto_escalation=True` y respuesta vacía.
- **Post-generación** valida alucinaciones y descuentos (`validate_generated_response`), marcando `auto_hallucination`, `auto_discount` y `blocked_reason`.
- Usa `PromptAssemblyService.assemble()`: prompt de sistema con reglas de negocio activas + tono de "asistente nocturno", ejemplos few-shot curados seleccionados por solape de palabras clave, y datos de la propiedad en vivo (`fetch_live_property_data`).
- Los borradores pasan a cola de revisión humana y pueden **promoverse a ejemplos few-shot** aprobados (cierra el loop de mejora: `.views.promote_draft`).

---

## 12. Dashboard y herramientas de control

### 12.1 Dashboard (`property_bot_dashboard`)
Ruta: `property-bot-dashboard:dashboard` (niveles de permiso 4–5).
- **KPIs:** total, respondidos, ignorados, en revisión, errores, latencia promedio, % por acción y desglose por veredicto humano.
- **Visualización por lead** (conversación), no por evento: si un hilo tuvo `respond_once`, muestra esa decisión.
- **Edición:** horario, `enabled`, plantillas de mensaje por tipo. Cada cambio se audita en `PropertyBotControlAudit`.

### 12.2 Detalle (`property_bot_interaction_detail`)
Muestra la evidencia completa de una decisión (`detail.html`).

### 12.3 Revisión humana (`property_bot_review`)
Permite marcar `confirmed_ok`/`confirmed_error` con nota. Usa los mismos permisos que el dashboard. Revisa los que quedaron `pending` (`TITLE_CODE_MISMATCH`, `MISSING_REQUIRED_DATA`, `INTERNAL_ERROR`).

### 12.4 Emulador (`property_bot_emulator`)
Entorno de prueba que llama a `process_initial_message` con la **misma lógica real** (sin flags especiales). Normaliza E.164 Perú (prefijo `+51` para móviles de 9 dígitos), admite payload JSON crudo y flag `human_takeover`.

---

## 13. Diccionario de `reason_code`

| Código | Significado | Acción |
|--------|-------------|--------|
| `ANSWER_SENT` | Respondió con la plantilla | `respond_once` |
| `DUPLICATE_MESSAGE` | Mismo `message_id` ya procesado | `ignore` (idempotente) |
| `ALREADY_RESPONDED` | El hilo ya recibió respuesta | `ignore` (one-shot) |
| `HUMAN_TAKEOVER` | Asesor humano tomó el hilo | `ignore` |
| `BOT_DISABLED` | `config.enabled=False` | `ignore` |
| `OUTSIDE_SCHEDULE` | Fuera de la ventana nocturna | `ignore` |
| `MISSING_CONVERSATION_ID` | Falta id externo y se requiere | `ignore` |
| `NO_PROPERTY_CODE` | No hay código `PROP...` | `ignore` |
| `MULTIPLE_PROPERTY_CODES` | Hay más de un código | `ignore` |
| `TITLE_CODE_MISMATCH` | El título no coincide con el código | `ignore` (pendiente revisión) |
| `PROPERTY_NOT_FOUND` | Código inexistente o duplicado en CRM | `ignore` |
| `UNSUPPORTED_PROPERTY_TYPE` | Tipo no configurado | `ignore` |
| `PROPERTY_NOT_PUBLISHABLE` | Invisible o estado vendida/pausada/etc. | `ignore` |
| `MISSING_REQUIRED_DATA` | Datos incompletos | `ignore` (pendiente revisión) |
| `VALIDATION_FAILED` | Guardrail de payload/render falló | `ignore` |
| `INTERNAL_ERROR` | Excepción técnica | `ignore` (error) |

---

## 14. Relaciones con el resto del sistema

### 14.1 `n8n_bridge.views` (chat libre)
No es el bot nocturno: es el **puente general** que reenvía mensajes de n8n al `ChatProcessor` (chat-web/canvas) con la app `whatsapp-n8n`, memoria y RAG. Comparte con el bot nocturno el helper `_get_or_create_lead` y la clase `ChatProcessor` (usada también por la memoria episódica del bot).

### 14.2 `intelligence`
- El bot nocturno es, formalmente, un **agente** (`AgenteRespuestaInicialWhatsApp`) con una **sola skill permitida** (`informacion_inicial_propiedad`), `max_iterations=1`, `budget_limit_usd=0.0`, que sobreescribe `resolve` para llamar la skill de forma directa (sin loop ReAct ni LLM).
- La skill consulta el CRM `propifai` con `SELECT` (capa de solo lectura).

### 14.3 `response_intelligence` (motor IA)
- El respondedor nocturno **produce datos** para el motor IA: cada mensaje real genera (si el shadow está activo) un `BotResponseDraft`. Ese borrador se evalúa, y los buenos se promueven como ejemplos few-shot que el propio `PromptAssemblyService` usa para mejorar el motor.
- El prompt del motor IA se define a sí mismo como "el asistente nocturno de una inmobiliaria en Arequipa, Perú", reutilizando la skill `informacion_inicial_propiedad` para traer datos en vivo.

### 14.4 CRM (`propifai`)
Fuente de datos de solo lectura (SELECT). La skill falla de forma determinista si el tipo no está mapeado o si la moneda no es soportada.

---

## 15. Seguridad y privacidad

- **API key** por header `X-N8N-API-Key` comparada con `hmac.compare_digest` (evita timing attacks).
- **Teléfono ofuscado**: solo se guarda `phone_last4`; se persiste `phone_hash` (HMAC-SHA256 con `SECRET_KEY`) y, en `PropertyBotInitialResponse.phone`, el número normalizado (revisado en dashboard solo por niveles 4–5).
- **Permissions**: dashboard/detalle/emulador/revisión requieren niveles `[4, 5]` (`has_permission`).
- Sin secretos en código; todo desde variables de entorno.

---

## 16. Tests existentes

Archivo: `webapp/n8n_bridge/tests/test_initial_property_bot.py`

| Clase | Cubre |
|-------|-------|
| `InitialPropertyDetectorTests` | Extracción/normalización de código, rechazo de múltiples códigos, coherencia de título |
| `InitialPropertyRendererTests` | Plantilla de casa con datos aprobados, plantilla de terreno con área |
| `ScheduleGuardTests` | Ventana horaria start-inclusive / end-exclusive |
| `EndpointContractTests` | Contrato one-shot del endpoint con API key |

---

## 17. Variables de entorno relevantes

| Variable | Uso | Default |
|----------|-----|---------|
| `N8N_BRIDGE_API_KEY` | API key de los endpoints del puente | vacío (deshabilitado) |
| `PROPERTY_INITIAL_BOT_ENABLED` | Habilitar el respondedor nocturno | `false` |
| `PROPERTY_INITIAL_BOT_START` | Inicio de la ventana | `00:00` |
| `PROPERTY_INITIAL_BOT_END` | Fin de la ventana | `05:00` |
| `PROPERTY_INITIAL_BOT_TIMEZONE` | Zona horaria | `America/Lima` |
| `PROPERTY_INITIAL_BOT_REQUIRE_CONVERSATION_ID` | Exigir id externo | `true` |
| `RESPONSE_INTELLIGENCE_SHADOW` | Activar shadow live (si no hay switch en BD) | `0` |

---

## 18. Consideraciones de mantenimiento / mejoras potenciales

1. **Config por entorno vs BD:** hoy `get_bot_configuration()` crea el singleton con defaults desde env; la fuente de verdad se vuelve DB tras la primera ejecución. Revisar precedencia (env no sobreescribe una fila ya creada).
2. **`phone` plano en DB:** además del hash se guarda el número completo; evaluar si el dashboard necesita realmente el número intacto o solo `phone_last4`.
3. **Shadow hilo daemon:** `spawn_shadow_draft` corre en `threading.Thread`; en despliegues multi-worker conviene verificar comportamiento ante tareas largas/bloqueo.
4. **One-shot rígido:** el flag `ALREADY_RESPONDED` es definitivo por hilo; considerar política de reapertura si el lead retoma el contacto en horario hábil.
5. **Cobertura de tests:** el flujo de `process_initial_message` completo (guardias + persistencia + memoria) aún no tiene tests de integración aislados del CRM.

---

*Fuentes principales: `webapp/n8n_bridge/` + `webapp/intelligence/agents&skills` + `webapp/response_intelligence/`.*
