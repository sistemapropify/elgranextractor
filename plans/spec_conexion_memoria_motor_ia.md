# Spec: Conectar Memoria Conversacional (y Episódica) al Motor de Respuestas IA

> Módulo afectado: `webapp/response_intelligence/prompt_assembly.py`
> Memoria a integrar: `MemoryService` (conversacional, `webapp/intelligence/services/memory.py`)
> Memoria complementaria (fase 2 de este fix): `EpisodicMemoryService`
> Este documento usa **únicamente** las funciones documentadas en el análisis de arquitectura
> de memorias que proporcionaste. Donde la firma exacta (parámetros, tipo de retorno) no está
> especificada en ese documento, se marca explícitamente como **[VERIFICAR EN CÓDIGO]** en vez
> de asumirla.

---

## 1. Objetivo

Que `PromptAssemblyService.assemble()` deje de generar cada respuesta de forma aislada
("amnésica") y en su lugar incorpore el contexto real de la conversación en curso —
usando la memoria conversacional que ya existe (`Conversation` / `MemoryService`), sin
crear un sistema de memoria nuevo.

---

## 2. Qué se conecta y qué no (alcance de esta spec)

| Pieza | Acción |
|---|---|
| `MemoryService` (conversacional) | **Conectar ahora** — es el objetivo principal de esta spec |
| `EpisodicMemoryService` (lectura) | **Fase 2, spec aparte** — hoy solo se escribe (`save_episode`), no se lee en ningún flujo de producción según el hallazgo #2 de tu documento. Conectar su lectura implica más superficie (embeddings, similitud coseno) y merece su propia validación en sandbox antes de tocarla |
| `Fact` (hechos) | **Fuera de alcance por ahora** — útil a futuro para preferencias del lead, no crítico para el bug actual |
| Memoria nueva | **No se crea** — confirmado en la conversación anterior que no hace falta |

---

## 3. Cambio principal en `PromptAssemblyService.assemble()`

### 3.1 Qué debe pasar, en orden

1. Resolver la identidad/sesión del lead ante `MemoryService` para poder cargar contexto.
2. Cargar el contexto conversacional reciente (mensajes + resumen + hechos top-10).
3. Detectar si el mensaje actual trae un código de propiedad nuevo (`extract_property_identity`,
   ya usado en el respondedor nocturno).
4. Si no trae código nuevo, resolver el `property_id` desde el contexto de la conversación
   ya cargada, o como fallback desde `PropertyBotInitialResponse.conversation_property_key`
   (esto ya está documentado y confirmado en el análisis del respondedor nocturno).
5. Traer datos reales de la propiedad (`fetch_live_property_data`, ya existente en
   `response_intelligence`).
6. Armar el prompt final con: reglas de negocio + few-shot + datos de propiedad +
   **contexto conversacional cargado en el paso 2**.

### 3.2 Pseudocódigo (solo con funciones confirmadas)

```python
from webapp.intelligence.services.memory import MemoryService
from webapp.n8n_bridge.services.initial_property_detector import extract_property_identity

class PromptAssemblyService:

    def assemble(self, lead_id, client_message, ...):
        memory = MemoryService()

        # [VERIFICAR EN CÓDIGO] parámetros reales de get_or_create_user():
        # el documento indica que busca/crea por phone/email, pero no confirma
        # si response_intelligence ya tiene ese dato disponible en este punto
        # del flujo, o si hay que resolverlo primero desde PropertyBotInitialResponse
        # (que sí guarda phone_hash / phone_last4 / phone).
        user = memory.get_or_create_user(...)

        # [VERIFICAR EN CÓDIGO] parámetros de get_active_session() y
        # load_conversation_context(): el documento no especifica si reciben
        # el user, un identificador de sesión, o ambos.
        session = memory.get_active_session(...)
        conversation_context = memory.load_conversation_context(session)

        # Esto sí está confirmado y ya en uso en n8n_bridge:
        detected = extract_property_identity(client_message)

        property_id = detected.property_id if detected and detected.property_id else None
        if not property_id:
            property_id = self._property_id_from_conversation_context(conversation_context)
        if not property_id:
            property_id = self._property_id_from_initial_response(lead_id)  # fallback documentado

        property_data = self.fetch_live_property_data(property_id) if property_id else None

        few_shot = self.select_few_shot(client_message)
        business_rules = self.build_system_prompt()

        prompt = self._build_prompt(
            business_rules=business_rules,
            few_shot=few_shot,
            property_data=property_data,
            conversation_context=conversation_context,  # <- lo nuevo
        )
        return prompt
```

### 3.3 Guardar el turno de vuelta en memoria

`MemoryService.save_message()` está documentado como la función de escritura de la
memoria conversacional. Después de que el motor IA genera una respuesta (incluso en
modo shadow, donde no se envía pero sí conviene simular el guardado para probar el
flujo completo en sandbox), debe llamarse para que el siguiente turno del lead ya
encuentre el mensaje anterior en el contexto.

```python
# [VERIFICAR EN CÓDIGO] firma exacta de save_message(): el documento no especifica
# si recibe (session, sender, text) o una estructura distinta.
memory.save_message(session, ...)
```

**Importante:** en modo `shadow_live`, evaluar si conviene guardar en la memoria real o
en una copia aislada — guardar en la memoria real de producción durante shadow podría
contaminar el contexto que luego usaría el flujo de producción (chat libre / respondedor
nocturno) si conviven en la misma sesión. Esto se define en la sección 5.

---

## 4. Resolución de `property_id` — fallback documentado (sin inventar nada)

Esta parte ya se puede especificar con confianza porque está en el documento del
respondedor nocturno:

```python
def _property_id_from_initial_response(self, lead_id):
    from webapp.n8n_bridge.models import PropertyBotInitialResponse
    return (
        PropertyBotInitialResponse.objects
        .filter(...)  # [VERIFICAR EN CÓDIGO] el campo exacto para filtrar por lead_id
                       # — el modelo documentado tiene conversation_property_key,
                       # external_conversation_id y phone_hash, pero no se confirmó
                       # cuál de ellos es la forma correcta de vincular con lead_id
                       # del lado de response_intelligence.
        .values_list("property_id", flat=True)
        .first()
    )
```

Este es el único punto de la spec anterior (fix del bug) que sigue teniendo una
incógnita real: **cómo se relaciona el `lead_id` que usa `response_intelligence` con
`PropertyBotInitialResponse`**, que se identifica por teléfono/hilo, no por `lead_id`
del CRM directamente. Hay que confirmar en el código si ya existe esa relación (por
ejemplo, si `PropertyBotInitialResponse` guarda también el `lead_id` del CRM en algún
campo no documentado aquí) antes de escribir el filtro real.

---

## 5. Riesgos a resolver antes de implementar (explícitos, no asumidos)

1. **Bug conocido a evitar como plantilla de error:** tu propio documento señala que
   `context_agent.py` llama a `memory.get_user_facts(user_id)`, un método que no existe
   en `MemoryService`, y el error queda silenciado por un `except`. Antes de integrar,
   confirmar contra el código real (no contra este documento) que `get_active_session`,
   `load_conversation_context` y `save_message` sí existen con esos nombres exactos y
   no son parte de la misma categoría de método "documentado pero no implementado".

2. **Carpeta duplicada:** existe una copia completa de `webapp/intelligence` en
   `elgranextractor/webapp/intelligence`. Confirmar cuál import path usa
   `response_intelligence` antes de tocar nada, para no editar o depender de la copia
   que no corre en producción.

3. **Contaminación de sesión en modo shadow:** si `Conversation` es una sesión única
   por lead (no por "flujo" — chat libre vs bot nocturno vs motor IA), hay que decidir
   si el motor IA en modo shadow debe leer la sesión real (para simular fielmente lo
   que pasaría en producción) pero **sin escribir** en ella, para no interferir con lo
   que ve el chat libre o el respondedor nocturno mientras el motor IA sigue en pruebas.

4. **Ventana de 24h vs "hasta las 9am":** la memoria conversacional documentada usa una
   ventana fija de 24h. Confirmar que esto cubre el caso real (de medianoche a 9am son
   menos de 24h, así que debería ser suficiente), pero vale la pena verificarlo con un
   caso límite: un lead que escribió por primera vez a las 23:50 del día anterior.

---

## 6. Plan de implementación

1. **Confirmar en código** (no en este documento) las firmas exactas de
   `get_or_create_user`, `get_active_session`, `load_conversation_context` y
   `save_message`, y resolver la incógnita de la sección 4 (vínculo `lead_id` ↔
   `PropertyBotInitialResponse`).
2. Implementar el cambio en `PromptAssemblyService.assemble()` (sección 3.2).
3. Probar en **sandbox offline** (Nivel 1, ya definido en la spec original) sobre los
   dos casos reales que ya fallaron: primera pregunta con código, y repregunta sin
   código ("¿cuál es el método de pago?").
4. Confirmar que la respuesta de la repregunta usa el `property_id` correcto sin
   pedírselo de nuevo al lead.
5. Reactivar `shadow_live` (ya está en ese modo) y revisar la cola de
   `BotResponseDraft` durante 24-48h con este cambio antes de considerar volver a
   producción.

---

## 7. Lo que esta spec deliberadamente NO incluye

- Conexión a `EpisodicMemoryService` (lectura) — fase 2, spec aparte.
- Conexión a `Fact` (hechos) — no es necesario para resolver el bug actual.
- Cualquier función o firma de `MemoryService`/`EpisodicMemoryService` no confirmada
  explícitamente en el documento de arquitectura de memorias que compartiste. Todo lo
  marcado **[VERIFICAR EN CÓDIGO]** debe resolverse leyendo el código fuente real antes
  de implementar, no asumirse desde esta spec.
