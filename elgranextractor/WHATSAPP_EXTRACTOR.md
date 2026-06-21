# Extractor de WhatsApp — Documentación Técnica

## ¿Qué hace?

El extractor de WhatsApp procesa archivos `.txt` exportados de chats de WhatsApp (grupos inmobiliarios) y extrae **requerimientos** (demanda de propiedades) estructurados en la tabla `Requerimiento`.

Ejemplo de entrada:
```
16/01/26, 10:30 - Juan Pérez: Alquilo duplex de 160m2 en Cayma, 3 dormitorios, 2 baños, presupuesto 2000 soles
```

Ejemplo de salida (en BD):
| Campo | Valor |
|---|---|
| `tipo_propiedad` | departamento |
| `distritos` | Cayma |
| `area_m2` | 160 |
| `habitaciones` | 3 |
| `banos` | 2 |
| `presupuesto_monto` | 2000 |
| `presupuesto_moneda` | soles |

---

## Arquitectura

```
Archivo .txt
    │
    ▼
┌─────────────────────────────┐
│  WhatsAppTxtParser          │  ← Parsea el .txt en mensajes individuales
│  (whatsapp_txt_parser.py)   │     Extrae: autor, fecha, hora, texto
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│  TextNormalizer             │  ← Limpia el texto (emojis, URLs, HTML)
│  (text_normalizer.py)       │     Salida: texto_limpio
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│  DeduplicadorIA             │  ← Verifica si el mensaje ya existe en BD
│  (deduplicacion_ia.py)      │     (compara por texto + agente)
└─────────────────────────────┘
    │  (si es duplicado → se salta)
    ▼
┌──────────────────────────────────────────────┐
│  DeepSeekTransformer.transformar()           │  ← Extracción IA
│  (deepseek_transformer.py)                   │
│                                              │
│  ┌──────────────────────────────────────┐    │
│  │  1. _ejecutar_skill()                │    │  ← Intenta con el skill
│  │     → SkillOrchestrator              │    │     (clasificar_intencion_whatsapp)
│  │     → ClasificarIntencionWhatsAppSkill│    │
│  │     → LLMService.extract_structured()│    │     Llama a DeepSeek API
│  │     → _mapear_campos()               │    │     Mapea + regex fallback
│  └──────────────────────────────────────┘    │
│         │ (si falla)                         │
│         ▼                                    │
│  ┌──────────────────────────────────────┐    │
│  │  2. _transformar_legacy()            │    │  ← Fallback legacy
│  │     → LLMService.extract_structured()│    │     Llama a DeepSeek API
│  │     → _mapear_campos()               │    │     Mapea + regex fallback
│  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│  tasks.py                   │  ← Crea el Requerimiento en BD
│  (procesar_archivo_extraccion)│    Aplica regex fallback UNIVERSAL
│                              │    en area_m2, habitaciones, banos
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│  Requerimiento (BD)         │  ← Datos estructurados listos
└─────────────────────────────┘
```

---

## Flujo detallado

### 1. Parseo del archivo ([`WhatsAppTxtParser`](webapp/whatsapp_extractor/services/whatsapp_txt_parser.py))
- Lee el archivo `.txt` línea por línea
- Identifica el formato de chat de WhatsApp exportado
- Extrae por cada mensaje: `autor`, `fecha`, `hora`, `texto`, `agente_telefono`
- Detecta el nombre del grupo desde el nombre del archivo

### 2. Normalización ([`TextNormalizer.limpiar_texto()`](webapp/whatsapp_extractor/services/text_normalizer.py:109))
- Elimina emojis, URLs, HTML tags
- Normaliza espacios y saltos de línea
- **Nota**: El texto original se conserva en `msg['texto']` para el regex fallback

### 3. Deduplicación ([`DeduplicadorIA.verificar_duplicado_simple()`](webapp/whatsapp_extractor/services/deduplicacion_ia.py))
- Compara el texto normalizado contra requerimientos existentes
- Si coincide (mismo texto + mismo agente), se salta el mensaje

### 4. Extracción IA ([`DeepSeekTransformer.transformar()`](webapp/whatsapp_extractor/services/deepseek_transformer.py:84))
Dos caminos posibles:

#### Camino A — Skill (principal)
1. [`_ejecutar_skill()`](webapp/whatsapp_extractor/services/deepseek_transformer.py:115) → `SkillOrchestrator.execute_skill("clasificar_intencion_whatsapp")`
2. [`ClasificarIntencionWhatsAppSkill.execute()`](webapp/intelligence/skills/clasificar_intencion_whatsapp.py:178) → valida params, llama a DeepSeek
3. [`LLMService.extract_structured_data()`](webapp/intelligence/services/llm.py:924) → llama a DeepSeek API con prompt estructurado
4. [`_mapear_campos()`](webapp/intelligence/skills/clasificar_intencion_whatsapp.py:273) → mapea respuesta JSON a campos del modelo
   - Si DeepSeek no extrajo `area_m2` → aplica regex sobre el texto original
   - Si DeepSeek no extrajo `habitaciones` → aplica regex
   - Si DeepSeek no extrajo `banos` → aplica regex

#### Camino B — Legacy (fallback si el skill falla)
1. [`_transformar_legacy()`](webapp/whatsapp_extractor/services/deepseek_transformer.py:175) → llama a DeepSeek directamente
2. [`_mapear_campos()`](webapp/whatsapp_extractor/services/deepseek_transformer.py:254) → mismo mapeo con regex fallback

### 5. Creación del Requerimiento ([`tasks.py`](webapp/whatsapp_extractor/tasks.py:493))
- Toma los datos extraídos y crea un `Requerimiento` en BD
- **Fallo de seguridad**: Si DeepSeek no extrajo `area_m2`, `habitaciones` o `banos`, se aplica regex directamente sobre `texto_original` (el mensaje crudo sin normalizar)

---

## Extracción por Regex (Fallback Universal)

Cuando DeepSeek no logra extraer un campo numérico, se usan estos patrones regex directamente sobre el texto original del mensaje:

### Área (`area_m2`)
```python
# Patrón: "160m2", "40 m2", "200 metros cuadrados", "200 mts"
r'(\d{1,4}(?:[.,]\d{1,4})?)\s*(?:m[²2]|metros?\s*cuadrados?|metros|mts?|mt)\b'
```
- Captura: `160m2` → 160, `40 m2` → 40, `200 metros cuadrados` → 200
- Soporta formato peruano: `10,000 m2` → 10000 (coma como separador de miles)

### Habitaciones
```python
# Patrón: "3 dormitorios", "2 cuartos", "4 habitaciones", "3 hab"
r'(\d+)\s*(?:dormitorios?|cuartos?|habitaciones?|hab\.?\s*|dorm\.?\s*|hab\b|dorm\b)'
```

### Baños
```python
# Patrón: "2 baños", "1 bano", "2 ss.hh"
r'(\d+)\s*(?:baños?|banos?|bañ\.?\s*|ba\.?\s*|ss\.?\s*hh\.?|servicios\s+higiénicos)'
```

---

## Monitoreo de Errores

Los errores de extracción se registran en dos lugares:

### 1. Template de errores del sistema
**URL**: `http://127.0.0.1:8000/intelligence/errors/`
- Muestra errores de Skills (`SkillExecution`) y del Extractor WhatsApp (`LogEntry`)
- La hora se muestra en **America/Lima** (corregido)

### 2. Logs del extractor
- Durante el procesamiento, cada mensaje genera entradas en `LogEntry`
- Niveles: `INFO`, `WARNING`, `ERROR`
- Se pueden ver desde el template del extractor WhatsApp

---

## Campos que extrae

| Campo BD | Tipo | Fuente |
|---|---|---|
| `tipo_propiedad` | Choice | DeepSeek + mapeo |
| `condicion` | Choice | DeepSeek + mapeo |
| `distritos` | string | DeepSeek |
| `area_m2` | integer | DeepSeek → regex fallback |
| `habitaciones` | integer | DeepSeek → regex fallback |
| `banos` | integer | DeepSeek → regex fallback |
| `presupuesto_monto` | decimal | DeepSeek |
| `presupuesto_moneda` | Choice | DeepSeek + mapeo |
| `presupuesto_forma_pago` | Choice | DeepSeek + mapeo |
| `cochera` | Choice | DeepSeek + mapeo |
| `ascensor` | Choice | DeepSeek + mapeo |
| `amueblado` | Choice | DeepSeek + mapeo |
| `piso_preferencia` | string | DeepSeek |
| `caracteristicas_extra` | string | DeepSeek |
| `agente` | string | DeepSeek / encabezado |
| `agente_telefono` | string | Parser / DeepSeek |
| `fuente` | string | Nombre del grupo |
| `fecha` | date | Del mensaje |
| `hora` | time | Del mensaje |

---

## Archivos clave

| Archivo | Propósito |
|---|---|
| [`webapp/whatsapp_extractor/tasks.py`](webapp/whatsapp_extractor/tasks.py) | Tarea Celery principal. Orquesta todo el flujo. Regex fallback universal. |
| [`webapp/whatsapp_extractor/services/deepseek_transformer.py`](webapp/whatsapp_extractor/services/deepseek_transformer.py) | Transformer con skill + legacy fallback. Regex en `_mapear_campos()`. |
| [`webapp/intelligence/skills/clasificar_intencion_whatsapp.py`](webapp/intelligence/skills/clasificar_intencion_whatsapp.py) | Skill de clasificación. Llama a DeepSeek + regex fallback. |
| [`webapp/intelligence/services/llm.py`](webapp/intelligence/services/llm.py) | Servicio central de DeepSeek API. Prompt estructurado. |
| [`webapp/whatsapp_extractor/services/text_normalizer.py`](webapp/whatsapp_extractor/services/text_normalizer.py) | Limpieza de texto (emojis, URLs, HTML). |
| [`webapp/whatsapp_extractor/services/whatsapp_txt_parser.py`](webapp/whatsapp_extractor/services/whatsapp_txt_parser.py) | Parser de archivos .txt exportados de WhatsApp. |
| [`webapp/whatsapp_extractor/services/deduplicacion_ia.py`](webapp/whatsapp_extractor/services/deduplicacion_ia.py) | Deduplicación de mensajes. |
| [`webapp/_borrar_enero.py`](webapp/_borrar_enero.py) | Script para borrar registros de enero 2026. |
