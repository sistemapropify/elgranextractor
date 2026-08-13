# Diseño: Conectar Memoria Conversacional al Motor de Respuestas IA

> Resuelve todas las incógnitas `[VERIFICAR EN CÓDIGO]` de `plans/spec_conexion_memoria_motor_ia.md`
> contra el código real. Objetivo: que `PromptAssemblyService.assemble()` deje de responder
> "amnésico" cargando el contexto de la conversación desde `MemoryService`.

---

## 1. Hechos verificados en código (reemplazan los [VERIFICAR EN CÓDIGO])

### MemoryService — `webapp/intelligence/services/memory.py`
| Método | Firma real (confirmada) | Notas |
|---|---|---|
| `get_or_create_user` | `(identifier: str, channel='unknown', metadata=None) -> User` | Estático. `identifier` con `@` = email, si no = **phone**. Crea `User` con rol nivel 1 si no existe. |
| `get_active_session` | `(user_id, app_id: str, session_id: str|None) -> Conversation` | Estático. `app_id` es el PK de `AppConfig` (lo **auto-crea** si no existe). `session_id` es un string de hilo (opcional). Ventana activa 24h. Devuelve la `Conversation`. |
| `load_conversation_context` | `(session_id: uuid) -> dict` | **El parámetro es el PK de `Conversation`** (no el campo `session_id` string). Devuelve `{messages[-10:], facts top10, summary, user_id, session_id}`. |
| `save_message` | `(session_id: uuid, role: 'user'|'assistant', content) -> None` | El parámetro es el **PK de `Conversation`**. Summary automático >20 msgs. |
| `get_user_facts` | **NO EXISTE** | `intelligence/agents/context_agent.py:74` la llama → **bug latente silencioso** (fuera de alcance; follow-up aparte). |

### Quién llama a `assemble()` (2 sitios, ambos ya tienen identidad)
1. `generate_draft_responses._process_lead(row, ...)` — `row` trae del CRM: `id` (lead_id), `phone`, `id_chatwoot`, `chat_history`. Llama `assemble(client_message, intent_category, property_code)`.
2. `shadow.maybe_generate_shadow_draft(*, lead_id, client_message, thread_id, intent_category, property_code)` — tiene `lead_id` y `thread_id`.

### Detección de propiedad
- `extract_property_identity(text)` → devuelve **dict** `{"codes": ["PROP000265", ...], "title_hint": "..."}`. **NO** tiene `.property_id` (el pseudocódigo de la spec lo asumía mal). `property_code = codes[0] if codes else ""`.

### Fallback `PropertyBotInitialResponse` — `webapp/n8n_bridge/models.py`
- Campos: `external_conversation_id`, `conversation_property_key`, `phone_hash`, `phone_last4`, `phone`, `property_id`, `property_code`. **NO tiene `lead_id`**.
- Respuesta a la incógnita de la spec §4: el vínculo con `response_intelligence` es por **teléfono** (`phone`/`phone_last4`) o por **hilo** (`external_conversation_id` = `thread_id`/`id_chatwoot`), no por `lead_id`.

### Duplicado de carpeta
- `response_intelligence` importa `intelligence.*` de `webapp/intelligence` (top-level). La copia `elgranextractor/webapp/intelligence` **no se usa** en producción.

---

## 2. Decisiones de diseño

### D1 — Identidad de memoria (quién es el "user")
- Resolver `User` por **phone** real del CRM cuando esté disponible (`get_or_create_user(phone, channel='whatsapp')`).
- Fallback si no hay phone: identificador sintético `lead:{lead_id}` (vía `get_or_create_user` → se guarda en el campo phone, aceptable).
- En shadow (solo `thread_id`/`lead_id`): intentar obtener phone desde `PropertyBotInitialResponse` por `external_conversation_id=thread_id`; si no, `lead:{lead_id}`.

### D2 — `app_id` (aislamiento entre flujos)
- Usar un `AppConfig` dedicado del motor: **`motor-ia-whatsapp`** (se auto-crea vía `get_active_session`). Esto **aísla** la memoria del motor del chat libre (`chat-web`) y del respondedor nocturno (que usa `n8n_bridge`, no `MemoryService`). Con esto, escribir en shadow **no contamina** otros flujos.

### D3 — `session_id` (hilo)
- Pasar el hilo real como `session_id`: `thread_id` (shadow) o `row["id_chatwoot"]` (generate_draft_responses) si viene; si no, `None` → reutiliza la sesión activa reciente del user+app (24h).

### D4 — Política de escritura según modo
- **Lectura (contexto):** siempre en los 3 modos (fail-open: si algo falla → contexto vacío, no rompe el prompt).
- **Escritura de memoria:**
  - `production`: guardar turno del cliente (`user`) **y** la respuesta del motor (`assistant`).
  - `sandbox`: guardar solo el turno del cliente (no la respuesta simulada) — o nada; decisión menor.
  - `shadow_live`: **solo lectura** (el borrador no se envía; no se escribe). Al estar aislado por `app_id`, leer la sesión real simula fielmente sin contaminar.

### D5 — Resolución de `property_code` (orden)
1. Si `property_code` ya viene (call-site) → se usa.
2. Del mensaje actual vía `extract_property_identity(client_message)` → `codes[0]`.
3. Del contexto de memoria (buscar `PROP...` en `context["messages"]`).
4. De `PropertyBotInitialResponse` (por `phone` o por `external_conversation_id=thread_id`) → `property_code`/`property_id`.
5. Si nada → sin datos de propiedad (comportamiento actual).

---

## 3. Cambios propuestos

### 3.1 `webapp/response_intelligence/memory_bridge.py` (nuevo, pequeño)
Helpers sin lógica de negocio:
- `resolve_user(phone, lead_id) -> User` (D1, fail-open → None)
- `resolve_session(user, thread_id) -> Conversation|None` (D2/D3, fail-open → None)
- `load_context(conversation) -> dict` (envuelve `load_conversation_context`; fail-open → {})
- `property_code_from_context(context) -> str`
- `property_code_from_initial_response(phone, thread_id) -> str` (D5.4)
- `save_turn(conversation, role, content)` (fail-open)

### 3.2 `webapp/response_intelligence/prompt_assembly.py` — `assemble()`
Firma **aditiva** (no rompe los tests/llamadas actuales):
```python
assemble(cls, client_message, intent_category="", property_code="", *,
         lead_id=None, phone=None, thread_id=None, app_id="motor-ia-whatsapp")
```
Flujo dentro de `assemble()`:
1. `context = memory_bridge.load_context(...)` (D1+D2+D3; fail-open → `{}`).
2. Si `property_code` vacío → resolver con D5 (mensaje → memoria → initial_response).
3. `fetch_live_property_data(property_code)` (si hay código).
4. Inyectar bloque `CONTEXTO DE LA CONVERSACIÓN` (mensajes recientes + resumen) en `user_prompt`, entre few-shot y datos de propiedad.
5. Retornar además `"memory": {"conversation_id", "user_id", "app_id"}` para que el call-site pueda escribir el turno.

### 3.3 Call-sites
- `generate_draft_responses._process_lead`: pasar `lead_id=row["id"]`, `phone=row.get("phone")`, `thread_id=row.get("id_chatwoot")`. Tras generar: si modo `production` → `save_turn(conv, 'user', text)` y `save_turn(conv, 'assistant', response)`; si `sandbox` → solo `user`.
- `shadow.maybe_generate_shadow_draft`: pasar `lead_id`, `thread_id`. Solo lectura (no escribe).

### 3.4 Out of scope (confirmado de la spec)
- `EpisodicMemoryService` (lectura) — fase 2.
- `Fact` — no necesario.
- Bug `context_agent.get_user_facts` — follow-up aparte (se documenta, no se toca aquí).

---

## 4. Riesgos / mitigaciones

| Riesgo | Mitigación |
|---|---|
| `get_or_create_user` race en threads (check→create) | Wrap en `get_or_create` con try/except (IntegrityError → `.get()`). Poco probable en sandbox. |
| Memoria falla en runtime | **Fail-open**: cualquier error de memoria → contexto vacío, prompt igual al actual. No rompe producción. |
| Tests existentes sin BD (`test_assemble_armar_prompt`) | `assemble` aditivo + fail-open → en SimpleTestCase la resolución de memoria se atrapa y no rompe. |
| Contaminación entre flujos | `app_id` dedicado `motor-ia-whatsapp` aísla; shadow es solo lectura. |
| Ventana 24h (caso 23:50 → 9am) | `SESSION_TIMEOUT_HOURS=24` cubre el caso real (de medianoche a 9am < 24h). |

---

## 5. Verificación (especificación de la spec §6.3-6.5)
1. Tests unitarios (SimpleTestCase, sin BD): orden de resolución de `property_code`, bloque de contexto en el prompt, degradación sin memoria, uso de `extract_property_identity` como dict.
2. **Sandbox offline**: `generate_draft_responses --mode sandbox --lead-id <X>` en los 2 casos reales:
   - Caso A: primera pregunta con código (`PROP...`).
   - Caso B: **repregunta sin código** (ej. "¿cuál es el método de pago?") → debe resolver el `property_id` correcto sin volver a pedírselo al lead.
3. Revisar `prompt_snapshot` del draft: debe incluir el bloque de contexto.
4. Dejar `shadow_live` activo y revisar cola `BotResponseDraft` 24-48h antes de pasar a producción.

---

## 6. Pasos de implementación (orden)
1. Crear `memory_bridge.py` con helpers (D1-D5).
2. Modificar `assemble()` (aditivo + fail-open + bloque de contexto + fallback property).
3. Actualizar los 2 call-sites (D4).
4. Tests unitarios (sin BD) + correr suite `response_intelligence` y `lead_intelligence`.
5. Sandbox offline en los 2 casos reales (verificación §5).
6. Commit + push (deploy) y seguimiento de shadow 24-48h.
