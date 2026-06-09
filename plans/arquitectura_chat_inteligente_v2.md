# Arquitectura Chat Inteligente v2 — Agente conversacional con skills

## Problema
El sistema actual separa:
- `resolver_contexto` (extrae parámetros)
- `context_manager` (guarda filtros)
- Routing de skills por keywords
- `chat_processor` decide si es seguimiento con reglas duras

DeepSeek no ve la conversación completa, solo fragmentos.

## Solución: DeepSeek como agente orquestador

DeepSeek ve la CONVERSACIÓN COMPLETA y decide QUÉ skill ejecutar y CON QUÉ parámetros. Así como Claude decide qué tool usar, DeepSeek decide qué skill del sistema invocar.

### Nuevo flujo

```
Usuario: "propiedades en Cayma"

  ┌─ Paso 1: DeepSeek analiza y decide skill ───────────┐
  │  Prompt:                                               │
  │  "Eres un agente inmobiliario. Tienes estas skills:    │
  │                                                        │
  │   1. busqueda_propiedades: busca propiedades por        │
  │      distrito, tipo, precio, etc.                       │
  │      Params: distrito, tipo_propiedad, operacion...     │
  │                                                        │
  │   2. acm_analisis: análisis comparativo de mercado      │
  │      Params: distrito, tipo_propiedad                   │
  │                                                        │
  │   3. matching_oferta_demanda: matching propiedades      │
  │      con requerimientos de clientes                     │
  │                                                        │
  │  HISTORIAL: []                                          │
  │  MENSAJE: 'propiedades en Cayma'                        │
  │                                                        │
  │  Responde SOLO con el JSON de la skill a ejecutar:      │
  │  {"skill": "busqueda_propiedades",                       │
  │   "params": {"distrito": "Cayma"},                      │
  │   "respuesta directa": null}  ← si puede responder sin  │
  │                                ejecutar una skill       │
  └──────────────────────────────────────────────────────┘

  ┌─ Paso 2: Sistema ejecuta la skill ──────────────────┐
  │  Ejecuta busqueda_propiedades(distrito="Cayma")      │
  │  Retorna: [5 propiedades en Cayma]                   │
  └──────────────────────────────────────────────────────┘

  ┌─ Paso 3: DeepSeek genera respuesta final ───────────┐
  │  Prompt:                                               │
  │  "HISTORIAL: []                                        │
  │   USUARIO: 'propiedades en Cayma'                      │
  │   SKILL EJECUTADA: busqueda_propiedades                │
  │   RESULTADOS: [5 propiedades en Cayma]                  │
  │                                                        │
  │   Genera una respuesta natural para el usuario."        │
  └──────────────────────────────────────────────────────┘


Usuario: "cuantas hay en total"

  ┌─ Paso 1: DeepSeek analiza con historial ────────────┐
  │  HISTORIAL: [                                          │
  │    Usuario: 'propiedades en Cayma'                     │
  │    Asistente: '[mostró 5 propiedades en Cayma]'        │
  │  ]                                                     │
  │  MENSAJE: 'cuantas hay en total'                       │
  │                                                        │
  │  DeepSeek entiende: "quiere total GENERAL,              │
  │  no solo Cayma"                                        │
  │  Responde: {"skill": "busqueda_propiedades",            │
  │             "params": {}}  ← sin filtros               │
  └──────────────────────────────────────────────────────┘

  ┌─ Paso 2: Sistema ejecuta skill sin filtros ─────────┐
  │  busqueda_propiedades(params={})                      │
  │  Retorna: 95 propiedades disponibles                  │
  └──────────────────────────────────────────────────────┘

  ┌─ Paso 3: DeepSeek genera respuesta ─────────────────┐
  │  "En total hay 95 propiedades disponibles            │
  │   en todos los distritos de Arequipa."               │
  └──────────────────────────────────────────────────────┘
```

### Componentes del sistema

#### 1. Registro de skills (ya existe: `skills/registry.py`)
Cada skill se registra con:
- `name`: identificador único
- `description`: qué hace y cuándo usarla
- `parameters`: JSON Schema de los parámetros que acepta

#### 2. Orquestador DeepSeek (nuevo: reemplaza `chat_processor`)
Un solo prompt que:
- Lista las skills disponibles con sus descripciones y parámetros
- Muestra el historial completo de la conversación
- DeepSeek decide: qué skill ejecutar (o si puede responder directamente)
- DeepSeek define los parámetros según el contexto conversacional

#### 3. Ejecutor de skills (ya existe: `skills/orchestrator.py`)
Ejecuta la skill que DeepSeek eligió y retorna los datos.

#### 4. Generador de respuesta (simplificado)
Toma el resultado de la skill + historial completo y DeepSeek genera la respuesta final.

### Skills disponibles para DeepSeek

```json
[
  {
    "name": "busqueda_propiedades",
    "description": "Buscar propiedades en venta o alquiler. Filtra por distrito, tipo, precio, habitaciones, etc.",
    "parameters": {
      "distrito": "string (opcional)",
      "tipo_propiedad": "string (opcional): Departamento, Casa, Terreno...",
      "operacion": "string (opcional): Venta, Alquiler",
      "precio_min": "number (opcional)",
      "precio_max": "number (opcional)",
      "condicion": "string (opcional): Disponible, Vendida..."
    }
  },
  {
    "name": "acm_analisis",
    "description": "Análisis Comparativo de Mercado. Precio por m2 en una zona.",
    "parameters": {
      "distrito": "string (requerido)",
      "tipo_propiedad": "string (opcional)"
    }
  },
  {
    "name": "matching_oferta_demanda",
    "description": "Encontrar propiedades que coinciden con requerimientos de clientes.",
    "parameters": {
      "requerimiento_id": "number (opcional)",
      "propiedad_id": "number (opcional)"
    }
  }
]
```

### Prompt del orquestador

```
Eres un agente inmobiliario inteligente. Tu objetivo es ayudar al usuario
con sus consultas sobre propiedades en Arequipa, Perú.

SKILLS DISPONIBLES:
{skills_list}

HISTORIAL DE CONVERSACIÓN:
{historial}

MENSAJE DEL USUARIO:
{mensaje}

INSTRUCCIONES:
1. Analiza el mensaje en el CONTEXTO COMPLETO del historial
2. Decide si necesitas ejecutar una SKILL para obtener datos
3. Si el usuario pregunta algo que puedes responder con el historial,
   responde directamente sin ejecutar skill
4. Si necesitas datos, elige la skill adecuada y sus parámetros
5. Los parámetros DEBEN inferirse del contexto conversacional completo

RESPONDE SOLO CON JSON:
{"skill": "nombre_de_skill" | null,
 "params": {parametros},
 "respuesta_directa": "respuesta si no necesita skill" | null}
```

### Archivos a modificar/crear

| Archivo | Acción |
|---------|--------|
| `services/chat_processor.py` | Reescribir: orquestador DeepSeek + ejecutor de skills |
| `skills/resolver_contexto.py` | Eliminar (ya no necesario) |
| `services/context_manager.py` | Eliminar (ya no necesario) |
| `services/prompts.py` | Nuevo prompt de orquestación |
| `skills/registry.py` | Mantener (ya funciona) |
| `skills/orchestrator.py` | Mantener (ya ejecuta skills) |

### Ventajas
- ✅ DeepSeek entiende la intención completa por el contexto conversacional
- ✅ Sin keywords, sin filtros duros, sin reglas de seguimiento
- ✅ DeepSeek sabe QUÉ skill usar y CON QUÉ parámetros
- ✅ El historial es el único contexto necesario
- ✅ Arquitectura identical a agentes con tools (Claude, GPT-4 with functions)
- ✅ Escalable: solo agregas skills nuevas y DeepSeek aprende a usarlas
