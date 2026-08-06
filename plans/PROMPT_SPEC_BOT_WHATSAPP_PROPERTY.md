# PROMPT PARA GENERAR LAS SPECS TÉCNICAS DEL BOT DE PROPIEDADES (WhatsApp / n8n)

Copia y pega TODO lo que está dentro del bloque `=== INICIO DEL PROMPT ===` / `=== FIN DEL PROMPT ===` en el modelo que va a redactar las especificaciones técnicas.

---

=== INICIO DEL PROMPT ===

Actúa como un arquitecto de software senior y redactor de especificaciones técnicas. Tu tarea es producir una **especificación técnica (SPEC) completa, concreta y accionable** para implementar un **bot de WhatsApp que responde información de una única propiedad inmobiliaria**, integrado con **n8n** dentro de un proyecto Django ya existente. La SPEC debe ser tan precisa que un desarrollador pueda implementarla sin ambigüedades.

## 1. CONTEXTO DEL PROYECTO
- Proyecto: **Propifai** (nombre técnico interno: Prometeo). SaaS PropTech de gestión inmobiliaria en Arequipa, Perú.
- Stack backend: **Django 5.0.6** + **Django REST Framework**, base de datos **Azure SQL (SQL Server)** con driver `mssql-django` (NO PostgreSQL; evitar funciones PostgreSQL-only). Procesamiento de Excel con Pandas/openpyxl.
- Apps relevantes:
  - `intelligence/` — Sistema de agentes y skills (AgentRegistry, SkillRegistry, SemanticSkillRouter). Ya registra 4 agentes: `agente_propiedades`, `agente_mercado`, `agente_requerimientos`, `agente_inteligencia_leads`. Incluye `intelligence/services/episodic_memory.py` (EpisodicMemoryService, tabla `intelligence_episodic_memory`) para memoria episódica.
  - `n8n_bridge/` — App puente de endpoints para conectar n8n/WhatsApp al chat existente (tiene `views.py`, `urls.py`).
  - `propifai/` — Portfolio propio de propiedades (tabla `property` en la BD `dbpropify_be`; specs en `property_specs`).
  - `lead_intelligence/` — Inteligencia de leads (no es el foco de esta SPEC).
- Convención de la base de datos: el código activo vive en `webapp/` en la raíz del repo. Nombres de apps en español, comandos de management en infinitivo español. No crear scripts sueltos en la raíz: los utilitarios van como comandos de management.

## 2. OBJETIVO
Construir un **agente de conversación por WhatsApp** (nuevo, dedicado) que:
- Detecte que el cliente pide información de **una propiedad específica** y responda **solo por esa propiedad**.
- Responda **estrictamente lo que el cliente pide** (área, dormitorios, precio, forma de pago, etc.) con reglas deterministas, no texto libre de la IA.
- Tenga **memoria episódica** por número de WhatsApp: recuerde la sesión actual y las sesiones anteriores del mismo cliente.
- Solo funcione en la **ventana 00:00–05:00 (hora de Perú)**; fuera de esa ventana **no responde nada** (el agente humano atiende).
- Envíe **solo el mensaje de la propiedad** (sin saludos, sin CTA, sin contenido extra).

## 3. REQUERIMIENTOS FUNCIONALES
1. **Detección de la propiedad:**
   - Por código: el cliente escribe algo como `PROP000261` → buscar por `code` exacto y responder esa única propiedad.
   - Por título/descripción: p. ej. `¡Hola! 👋 Más info sobre la casa de Urb. Colonial II (PROP000261)` → resolver el nombre/título a **una** propiedad. Si es ambiguo, el bot debe hacer **una pregunta de desambiguación** (nunca inventar ni responder varias).
2. **Filtros deterministas de respuesta (solo lo pedido):**
   - **Área** (según tipo: terrenos usan área total `land_area`; el resto `built_area`).
   - **Dormitorios/habitaciones** (`bedrooms` en `property_specs`).
   - **Precio** (`price` + `currency_name`; soles PEN o dólares USD).
   - **Forma de pago**, si el modelo lo tiene (verificar y documentar el campo exacto).
   - Si el cliente pide un dato concreto → responder SOLO ese dato. Si pide "toda la información" → resumen fijo de la propiedad. Nada más.
3. **Reglas de comportamiento (deterministas):**
   - Si el mensaje referencia una propiedad concreta → responder solo por esa propiedad.
   - Si no referencia una propiedad concreta → no responder ni recomendar otras; responder de forma acotada o con una pregunta.
   - Nunca inventar datos que no estén en la base.
4. **Memoria episódica:** por número de WhatsApp, guardar episodios (propiedad consultada, filtros pedidos, respuestas dadas, timestamp) y recuperar la sesión actual + anteriores para dar contexto (p. ej., "te envié el precio de PROP000261 hace 2 días").
5. **Ventana horaria:** activo solo de 00:00 a 05:00 hora Perú (`America/Lima`); fuera de la ventana el endpoint no responde (sin envío en n8n). Horas configurables por variables de entorno (`BOT_HORA_INICIO`, `BOT_HORA_FIN`).
6. **Integración n8n:** un endpoint (en `n8n_bridge` o el que decidas) que reciba el texto del cliente y el número de WhatsApp, despache al agente y devuelva la respuesta de texto estricta; n8n se encarga de enviar por WhatsApp.

## 4. COMPONENTES EXISTENTES A REUTILIZAR (no reinventar)
- `intelligence/skills/propiedades/skill.py` → `BusquedaPropiedadesSkill`: búsqueda híbrida (SQL + semántica), detección de filtros (distrito/tipo/precio/habitaciones/área/condición) y **búsqueda por nombre/título** con 3 estrategias (frases clave, prefijos, fuzzy). Reutilizar su detección de título/`code` para resolver a una propiedad; NO duplicar esa lógica.
- `intelligence/services/episodic_memory.py` → `EpisodicMemoryService` (memoria episódica).
- `intelligence/agents/` + `SkillRegistry` + `AgentRegistry` → patrón para registrar el nuevo agente.
- `n8n_bridge/` → patrón de endpoints para n8n/WhatsApp.
- `propifai/` y consultas SQL a `property` + `property_specs` (la skill ya tiene `_enriquecer_con_property_specs` como referencia de columnas reales: `bedrooms`, `bathrooms`, `land_area`, `built_area`, etc.).

## 5. ENTREGABLES DE LA SPEC (estructura mínima requerida)
1. **Arquitectura general** (diagrama de flujo texto o mermaid): WhatsApp → n8n → endpoint → despacho de agente → skill de propiedad específica → memoria episódica → respuesta estricta → n8n → WhatsApp.
2. **Despacho y detección de intención** (reglas deterministas): cómo distinguir consulta por código vs título vs filtro; umbrales y flujo de desambiguación.
3. **Skill nueva** `informacion_propiedad_especifica`: contrato (entrada/salida), lógica de resolución a 1 propiedad, selección estricta de campos, formato exacto del mensaje de respuesta (plantillas), y qué devolver cuando no se encuentra o es ambiguo.
4. **Agente nuevo** (nombre sugerido `agente_informacion_propiedad`): dominio, nivel de acceso, `allowed_skills`, y registro en `AgentRegistry`.
5. **Memoria episódica**: modelo/esquema por número de WhatsApp, API de lectura/escritura (sesión actual + anteriores), política de retención/pruning.
6. **Ventana horaria**: guardia de tiempo (`America/Lima`, horas configurables por env), qué devuelve fuera de la ventana.
7. **Endpoint n8n**: ruta, método, payload esperado (texto, número WhatsApp), respuesta (texto o vacío), autenticación/validación mínima.
8. **Configuración**: nuevas variables de entorno (con defaults) y dónde declararlas.
9. **Manejo de errores y edge cases**: propiedad inexistente, código mal formado, título ambiguo, mensaje fuera de horario, número sin sesión previa, campos faltantes (forma de pago ausente).
10. **Plan de implementación**: archivos a crear/modificar con rutas exactas bajo `webapp/`, orden de trabajo, y pruebas mínimas (unitarias para la skill y el guardia horario).

## 6. RESTRICCIONES DE LA SPEC
- Todo en español.
- Cumplir convenciones del proyecto: apps en español, comandos management en infinitivo, solo Django ORM (salvo SQL directo justificado, documentado), sin scripts sueltos en la raíz.
- La solución debe ser **determinista y estricta**: la IA solo se usa si es estrictamente necesaria; el núcleo de detección/responder es por reglas.
- Nombrar archivos y funciones concretos.

Entrega la SPEC como un documento Markdown técnico, completo y listo para implementar.

=== FIN DEL PROMPT ===
