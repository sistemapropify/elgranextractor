# 📜 EVOLUCIÓN DEL SISTEMA — SIIA / AIIA / Prometeo

> **La historia verdadera del sistema Propify, contada desde los commits, los errores y las batallas ganadas (y perdidas).**
>
> ⚠️ Este documento NO es marketing. Es la bitácora de guerra de un proyecto que empezó siendo una cosa y terminó siendo otra muy diferente.
>
> 📌 _Cada archivo mencionado es un enlace clickable al código original._

---

## 🌱 ENERO 2026 — Nace "El Gran Extractor"

### Lo que se prometió
> _"Un sistema que extrae propiedades de portales web peruanos (Urbania, Adondevivir, Remax, Properati) usando Selenium."_

### Lo que realmente pasó
El **30 de enero de 2026** se hizo el primer commit. Inmediatamente apareció el primer problema:

```
Commit: "Simplificar admin de semillas y aplicar monkey patch para error Django 5.0.6 con Python 3.14.2"
```

**Django 5.0.6 no era compatible con Python 3.14.2.** Hubo que aplicar un "monkey patch" —un parche quirúrgico— para que funcionara. Eso nunca es buena señal.

📁 El parche está en [`webapp/settings.py`](webapp/settings.py) (líneas ~288-310):
```python
# Monkey patch para Django 5.0.6 + Python 3.14
def patched_context_copy(self): ...
```

### 🕸️ El Scraping que nunca funcionó del todo
Se crearon los modelos `PropiedadRaw` y `FuenteWeb`, y scrapers para cada portal:

📁 [`webapp/ingestas/models.py`](webapp/ingestas/models.py) — Modelo principal
📁 [`webapp/semillas/`](webapp/semillas/) — Fuentes web
📁 [`webapp/captura/`](webapp/captura/) — Captura de URLs

**Pero los commits cuentan otra historia:**

```
Feb 16 — "Fix ingestas: corrección de formset y template validar.html"
Feb 16 — "Fix ingestas: manejo de importar_registros y corrección de importación"
Feb 16 — "Mejoras en validación de mapeos y carga de DataFrame"
Mar 05 — "Agrega campo subtipo_propiedad y corrige mapeo de importación Excel"
```

Cada dos días había que corregir algo. Los formularios no validaban bien, la importación de Excel fallaba, los mapeos de columnas estaban incorrectos. El scraping NUNCA llegó a ser 100% confiable.

> **Realidad**: El scraping con Selenium resultó frágil. Los portales cambiaban su HTML, las conexiones fallaban, y mantener los parsers era insostenible. Más tarde (Julio 2026) se planearía migrar a Playwright, pero nunca se ejecutó.

---

## 🔧 FEBRERO-MARZO 2026 — Dashboard y Visualización

### Lo que se prometió
> _"Dashboard de calidad de cartera con mapas, heatmaps y análisis de mercado."_

### Lo que realmente pasó
El ACM (Análisis Comparativo de Mercado) fue un éxito temprano:

```
Mar 03 — "feat(acm): Actualización automática del resumen al mover marcador"
Mar 03 — "Rediseño del resumen ACM: reducir altura a 2 filas, eliminar scroll"
Mar 03 — "Incluir propiedades de Propifai en ACM"
```

Pero el heatmap tuvo un bug trágico-cómico:

```
Mar 09 — "FIX: Heatmap ahora muestra TODAS las propiedades reales, no solo 2"
```

**¡Imagínate!** Durante semanas, el heatmap de precios solo mostraba **2 propiedades** en lugar de todas. Y nadie lo notó hasta que alguien dijo "algo huele mal aquí".

### 🗺️ La Guerra de los Mapas
Google Maps API funcionaba, pero:
- Los marcadores de propiedades propias y de competencia se confundían
- Los filtros por distrito a veces funcionaban, a veces no
- Las coordenadas de algunas propiedades estaben en blanco

📁 [`webapp/market_analysis/`](webapp/market_analysis/) — Donde vive el heatmap

---

## 🤖 FEBRERO 2026 — DeepSeek y la Promesa de la IA

### Lo que se prometió
> _"Procesamiento IA de propiedades con DeepSeek. El sistema entiende lenguaje natural."_

### Lo que realmente pasó
DeepSeek se integró rápido:

```
Feb 16 — "Implementación completa del módulo de requerimientos con integración de IA DeepSeek"
```

Y funcionó. Pero había un problema de fondo: **DeepSeek necesitaba datos de calidad para dar respuestas de calidad**, y los datos del scraping eran... irregulares.

📁 [`webapp/ingestas/procesamiento_ia.py`](webapp/ingestas/procesamiento_ia.py) — Procesamiento con DeepSeek

### 🧬 RAG: El Salvavidas
Para mejorar las respuestas sin depender del scraping, se implementó un sistema **RAG (Recuperación + Generación)**:

```
Jul 15 — "fix: semantic search as primary method, SQL filters as refinement"
Jul 15 — "raise similarity threshold from 0.3 to 0.65 to filter irrelevant results"
```

Se usó **FAISS** (Facebook AI Similarity Search) con embeddings **E5-small** en español:

📁 [`webapp/intelligence/rag/`](webapp/intelligence/rag/) — Motor RAG
📁 [`webapp/intelligence/faiss_index/`](webapp/intelligence/faiss_index/) — Índices vectoriales

**Otro bug silencioso:** El umbral de similitud estaba en 0.3, lo que significa que devolvía RESULTADOS BASURA (cosas que NO tenían nada que ver con lo preguntado). Se subió a 0.65 y la calidad mejoró drásticamente.

---

## ☁️ MARZO-ABRIL 2026 — La Pesadilla del Deploy en Azure

### Lo que se prometió
> _"Despliegue en Azure App Service. Setup sencillo."_

### Lo que realmente pasó
El **13 de marzo** comenzó la odisea. Miren la secuencia de commits de SOLO ESE DÍA:

```
Mar 13 10:38 — "Add or update the Azure App Service build and deployment workflow config"
Mar 13 11:11 — "fix settings"
Mar 13 11:47 — "fix azure import path for django apps"
Mar 13 12:01 — "add selenium for azure deploy"
Mar 13 14:38 — "fix staticfiles for azure"
```

**5 commits en 4 horas** solo para que el maldito deploy funcionara.

Y no terminó ahí. El **1 de abril**:

```
Abr 01 — "Fix: Comentar meta_ads en INSTALLED_APPS"
Abr 01 — "Fix: Ajustar configuración de despliegue para Azure"
Abr 01 — "Fix: Manejar importación fallida de market_analysis.charts"
Abr 01 — "Fix NameError: logger not defined in market_analysis/views.py"
Abr 01 — "Comment out analisis_crm.urls due to ModuleNotFoundError"
```

**5 errores de producción diferentes el mismo día.** Cada app nueva que se agregaba rompía el deploy porque:
- Los imports fallaban en producción aunque funcionaran local
- Los `logger` no estaban definidos donde se usaban
- Las apps parcialmente implementadas bloqueaban todo el sistema

### 🏥 El Zapato Inglés del Startup
El sistema de inicio (`startup.sh`) fue un constante dolor de cabeza. El **22 de julio** (¡ayer/hoy!) seguimos arreglándolo:

📁 [`webapp/startup.sh`](webapp/startup.sh) — Script de inicio

```
Jul 20 — "fix: ODBC driver install, restore __init__.py, consolidate startup configs"
Jul 22 — "fix: startup.sh busca manage.py en webapp/ y ruta temp dinamica"
Jul 22 — "fix: eliminar startup_command de appsvc.yaml, Oryx debe usar Procfile"
```

**El problema**: Azure Oryx extrae los archivos a `/tmp/8dee*/` (cambia cada deploy), pero el comando de inicio apuntaba a `/home/site/wwwroot/startup.sh` que NO EXISTÍA. La app nunca arrancaba y nadie entendía por qué. Después de 3 intentos, la solución fue: **borrar el comando de inicio y dejar que Azure use el Procfile**.

---

## 🎨 JULIO 2026 — El Canvas: Donde Todo se Conecta

### Lo que se prometió
> _"Un editor visual tipo pizarra para agentes inmobiliarios."_

### Lo que realmente pasó
El canvas empezó siendo un experimento y terminó siendo el centro del sistema. Pero el camino fue PEDREGOSO.

#### 🐛 Bugs de Snapshot (el terror de los usuarios)
Cada vez que un usuario guardaba y cargaba un canvas, los nodos se convertían en notas genéricas, se perdían las conexiones, o explotaba todo:

```
Jul 14 23:00 — "fix: lead analysis snapshot carga con field_data.prop_id como fallback"
Jul 14 23:11 — "debug: logs en refresh lead_analysis snapshot para diagnosticar"
Jul 14 23:22 — "fix: click handler despues de innerHTML + lead_nodo en restoreSnapshot"
Jul 14 23:50 — "fix: render lead_nodo en placeholder - evitaba que se conviertan en nota generica"
Jul 15 10:30 — "fix: lead analysis granularity context menu, undo batching, and label persistence"
Jul 15 10:38 — "fix: edges desync after undo/redo lead analysis refresh"
Jul 15 10:40 — "fix: lead analysis node shrinks after undo/redo"
```

**7 commits para arreglar el guardado y la restauración.** El `restoreSnapshot()` y `renderPlaceholderNodes()` fueron modificados decenas de veces. Cada tipo de nodo nuevo requería parches en ambos.

📁 [`webapp/canvas/static/canvas/js/canvas_nodes.js`](webapp/canvas/static/canvas/js/canvas_nodes.js) — La bestia de ~2800 líneas
📁 [`webapp/canvas/static/canvas/js/canvas_history.js`](webapp/canvas/static/canvas/js/canvas_history.js) — Sistema de undo/redo

#### 🔄 El Baile de Versiones (Cache-Busting)
Cada fix requería cambiar el `?v=N` en el nombre del archivo JS para que el navegador no usara la versión cacheada. Miren esta secuencia:

```
Jul 14 — "bump canvas_nodes.js cache buster v10→v11"
Jul 14 — "chore: bump JS version to force cache refresh"
Jul 14 — "add console log marker en canvas_nodes.js para verificar version"
Jul 15 — "fix: cache-busting canvas_nodes.js v12->v13"
Jul 15 — "fix: cache-busting canvas_history.js v5->v6"
Jul 21 — "fix: add cache-busting and debug log for lead matrix"
Jul 21 — "chore: bump JS version to force cache refresh"
Jul 22 — "fix: cache-busting (multiple versions v14→v25)"
```

**El versionado manual es un infierno.** Cada cambio requería acordarse de cambiar el número. Si se olvidaba, los usuarios seguían viendo la versión rota y reportaban errores que ya estaban "arreglados".

#### 💥 La Guerra de las Zonas Horarias
Las fechas de los leads estaban en UTC, pero el sistema se usa en Perú (UTC-5):

```
Jul 14 — "fix: convertir UTC a hora Peru en lead nodes"
Jul 15 — "debug: logs en lead node para diagnosticar hora"
Jul 15 — "fix: convertir UTC a Peru en Python (backend) en lugar de JS"
Apr 01 — "Aplicar conversión de zona horaria a todas las fechas de etapas y eventos"
```

Se intentó corregir en JavaScript, no funcionó. Se agregaron logs de depuración. Finalmente se corrigió en el backend con `SWITCHOFFSET`.

#### 📊 La Tragedia del Excel
La exportación a Excel tuvo **¡6 intentos!** en menos de 1 hora:

```
00:34 — "feat: add totals row and Excel export to lead matrix"  (intento 1)
00:38 — "fix: change Excel export to .htm"                      (intento 2)
00:40 — "fix: proper Excel XML format with mso header"          (intento 3)
00:41 — "fix: use SpreadsheetML XML format"                     (intento 4)
00:47 — "fix: use CSV format for Excel export"                  (intento 5)
00:49 — "feat: proper .xlsx export via backend (openpyxl)"      (intento 6, el bueno)
```

Intentamos HTML, luego XML de Microsoft, luego SpreadsheetML (otro XML), luego CSV, y finalmente **openpyxl** generando un `.xlsx` legítimo. Ese fue el que funcionó.

📁 [`webapp/canvas/views.py`](webapp/canvas/views.py) línea ~1527 — `api_export_lead_matrix`

#### 🔌 Las Aristas Invisibles (CSS faltante)
```
Jul 22 — MÚLTIPLES commits para que las líneas conectoras aparecieran
```

Resulta que las aristas se dibujaban en el SVG pero eran **invisibles** porque no tenían color definido en CSS. Se agregó `.cv-edge--visita { stroke: #e65100; }` y ¡puf! aparecieron mágicamente.

📁 [`webapp/canvas/static/canvas/css/canvas.css`](webapp/canvas/static/canvas/css/canvas.css) línea ~1158

---

## 🧠 JULIO 2026 — El Sistema de Agentes: El Refactor Más Grande

### Lo que se prometió
> _"Agentes IA que entienden lenguaje natural y ejecutan tareas inmobiliarias."_

### Lo que realmente pasó
El **19 de julio** se hizo el refactor más grande en la historia del proyecto:

```
Jul 19 17:01 — "feat: refactor plataforma agentes - Fases 1-8"
Jul 19 17:05 — "feat: refactor agentes - Fases 9 y 10"
```

**En 4 minutos** se movió TODO el sistema de agentes. En la práctica fueron muchas más horas de trabajo comprimidas en 2 commits.

### 🧟 El Formato Fantasma
Un bug sutil: el agente generaba requisitos de tipo `format` (formato) que nunca tenían skills asociados, pero el sistema se quedaba en un bucle tratando de satisfacerlos:

```
Jul 20 — "Implementacion completa del sistema de agentes con ReAct loop,
          precondiciones, requisitos monotonicos y eliminacion de formato fantasma"
```

📁 [`plans/SPEC_requisito_formato_fantasma.md`](plans/SPEC_requisito_formato_fantasma.md) — Documentación del bug

**Solución**: Filtrar los requisitos `format` en el mismo momento en que el LLM los genera, antes de que entren al ciclo de ejecución.

### 🌿 Contaminación de Skills
Otro bug: el agente intentaba skills de matemáticas (`suma`, `resta`) cuando el usuario preguntaba por propiedades:

📁 [`plans/SPEC_skill_contamination_taxonomia.md`](plans/SPEC_skill_contamination_taxonomia.md) — Documentación del bug

**Solución**: Clasificar los requisitos en 4 tipos: `data`, `comparison`, `matching`, `format`. Cada skill solo se ejecuta si su tipo coincide.

### 🚦 Error 504 Gateway Timeout
```
Jul 20 — "Fix: 504 GatewayTimeout + lead drag conflict + canvas API auth"
```

Las consultas de matching agotaban el tiempo de espera de Azure (230 segundos). Las propiedades se arrastraban en el canvas pero se solapaban con otros eventos. Y la autenticación del canvas a veces fallaba. **Un commit para 3 bugs diferentes.**

---

## 📊 LA MATRIZ DE LEADS (21-22 Julio 2026)

### La Función que Casi Mata el Proyecto
La matriz de leads fue la feature más compleja y con más bugs. En **2 días** hubo ~20 commits:

#### Día 1: Los Títulos Invisibles
```
Jul 21 10:14 — "fix: startup.sh deploy, skill contamination fix, lead matrix fix"
Jul 21 11:55 — "fix: lead-matrix JOIN property table for real titles"
Jul 21 11:59 — "fix: add cache-busting and debug log for lead matrix"
Jul 21 12:01 — "fix: remove merge logic, use direct titles from lead-matrix API"
```

**El problema**: La matriz mostraba números (IDs) en lugar de nombres de propiedades. Se intentó:
1. Unir con `IntelligenceDocument` → falló porque los IDs no coincidían
2. Unir con `properties` (tabla plural) → falló
3. Unir con `property` (tabla singular) → ¡funcionó!

Resulta que había **2 tablas de propiedades** y estábamos consultando la equivocada.

#### Día 2: Leads, Visitas y Excel
```
Jul 22 — ~15 commits en cascada
```

Cada fix generaba otro bug:
- Los scrollbars eran muy delgados → se agrandaron
- El Excel no se abría → 6 formatos diferentes hasta dar con openpyxl
- Los leads no se conectaban → faltaba CSS
- La tabla `event` se llamaba `events` en el código → pero era `event` en la BD
- Las columnas tenían nombres diferentes en la BD → `titulo` vs `title`, `fecha_evento` vs `start_time`
- El lead_status era "En visitas" no "Visitas" → se arregló el LIKE

---

## 💀 LA DEUDA TÉCNICA (Julio 2026)

### El Cementerio de Scripts
En la raíz del proyecto hay **300+ archivos** `test_*.py`, `check_*.py`, `debug_*.py`. Son reliquias de depuración que nadie se atrevió a borrar:

📁 [`d:/PROMETEO/`](.) — El cementerio

Entre ellos:
- `test_conexion_propifai.py` — ¿Sigue funcionando la conexión?
- `debug_propifai_terrenos.py` — Debug de terrenos de febrero
- `check_heatmap_live.py` — ¿El heatmap sigue vivo?
- `diagnostic_error.py`, `diagnostic_error2.py` — La secuela

### 🏚️ elgranextractor/ — El Gemelo Malvado
Hay una carpeta [`elgranextractor/`](elgranextractor/) que es una **copia duplicada** del proyecto. ¿Por qué? Misterio. Lo único que hace es confundir a cualquiera que intente entender el código.

### 🧵 Templates Duplicados
Múltiples templates tienen versiones `_backup`, `_debug`, `_clonado`. Hay que limpiar.

---

## 📈 LO QUE SÍ FUNCIONA (Para ser justos)

A pesar de todo, el sistema HOY:

| Feature | Estado | Desde |
|---|---|---|
| **ACM** (Comparativo de Mercado) | ✅ Estable | Marzo 2026 |
| **Matching Oferta-Demanda** | ✅ Estable | Julio 2026 |
| **Canvas con nodos** | ✅ Estable | Julio 2026 |
| **Matriz de Leads** | ✅ Estable | Julio 2026 |
| **Nodos de Visita** | ✅ Estable | Julio 2026 |
| **Chat con Agente IA** | ✅ Funcional | Julio 2026 |
| **Dashboard CRM** | 🔄 En desarrollo | Julio 2026 |
| **Scraping automático** | ⚠️ Frágil | Febrero 2026 |
| **Deploy en Azure** | ⚠️ Mejorando | Constante |

---

## 🎯 LECCIONES APRENDIDAS (Por si sirven)

1. **Los nombres de tablas importan.** `event` ≠ `events`, `property` ≠ `properties`. Revisa la BD antes de escribir código.

2. **El versionado manual de JS es un horror.** Hay que automatizarlo con hash en los nombres de archivo.

3. **Azure Oryx extrae en /tmp/**, no en /home/site/wwwroot/. No asumas rutas fijas.

4. **Cada nuevo tipo de nodo requiere parches en 4 lugares:** `createXNode()`, `restoreSnapshot()`, `renderPlaceholderNodes()`, `canvas_history.js`.

5. **SQL Server usa `SWITCHOFFSET`** para cambiar zona horaria, no `AT TIME ZONE`.

6. **Una tabla mal nombrada puede costar días.** Literalmente.

7. **Si el Excel no se abre, prueba con otro formato.** Eventualmente uno funcionará.

---

## 🚀 PRÓXIMOS PASOS (Los que sí vamos a hacer)

### Prioridad Alta (Fase A — IA Asistente)
- [ ] **pgvector / búsqueda semántica** — Migrar a PostgreSQL o evaluar alternativa
- [ ] **RAG sobre propiedades** — Pipeline completo embedding → search → respuesta
- [ ] **Chat asistente interno** — Chatbot en canvas para búsqueda en lenguaje natural
- [ ] **Validación inteligente** — Guardrails IA al ingresar propiedades

### Prioridad Media (Fase B — Scraping inteligente)
- [ ] **Playwright** — Reemplazar Selenium (que nunca funcionó del todo)
- [ ] **Pipeline de ingestión automática** — Celery Beat → scrapers → BD → embeddings
- [ ] **News intelligence** — Noticias inmobiliarias de Arequipa

### Prioridad Baja (Fase C — API pública)
- [ ] **FastAPI microservicio** — API independiente
- [ ] **Sistema de API Keys** — Multi-tenant, rate limiting
- [ ] **Documentación OpenAPI** — Para integración con terceros

### Deuda Técnica (Urgente)
- [ ] **Limpiar scripts del root** — Mover tests a `tests/`, eliminar debug scripts
- [ ] **Eliminar `elgranextractor/`** — Confirmar si sirve para algo, si no, borrar
- [ ] **Unificar API** — Consolidar `urls.py` y `urls_mejoradas.py`
- [ ] **Consolidar modelos Event** — Dos modelos iguales en `eventos/` y `propifai/`

---

## 📊 STATS REALES DEL PROYECTO

| Métrica | Valor |
|---|---|
| **Vida del proyecto** | 7 meses (Enero - Julio 2026) |
| **Commits** | ~200+ |
| **Commits de fix** | ~70% (estimado) |
| **Intentos de Excel** | 6 |
| **Veces que se rompió el deploy** | Innumerables |
| **Versiones de JS** | 25 (en 7 días) |
| **Scripts basura en el root** | 300+ |
| **Noches sin dormir** | Varias |

---

*Documento generado el 22 de Julio de 2026*
*Basado en el historial de commits REAL, no en lo que prometimos.*
*Este documento contiene la verdad. Toda ella.*

> *"No te enamores de tu código. Enamórate de resolver el problema."*
