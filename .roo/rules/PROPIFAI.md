# PROPIFAI — Documento Maestro de Contexto
> **Para agentes IA (Roo Code, Claude, Cursor):** Lee este archivo COMPLETO antes de tocar cualquier código.
> Este documento es la fuente de verdad del proyecto. Si algo aquí contradice el código, pregunta antes de asumir.

---

## 1. IDENTIDAD DEL PROYECTO

**Nombre comercial:** Propifai  
**Nombre técnico interno:** Prometeo (nombre del repositorio raíz)  
**Tipo:** PropTech SaaS — Plataforma de gestión e inteligencia inmobiliaria  
**Mercado actual:** Arequipa, Perú  
**Visión de escala:** Otras ciudades de Perú → Latinoamérica  
**Metodología:** Lean Startup — velocidad de iteración sobre perfección  
**Etapa:** Producción activa + desarrollo continuo de nuevas features  

---

## 2. STACK TECNOLÓGICO ACTUAL

### Backend
| Componente | Tecnología | Versión |
|---|---|---|
| Framework | Django | 5.0.6 |
| Base de datos | Azure SQL (SQL Server) | — |
| ORM driver | mssql-django | — |
| API REST | Django REST Framework | 3.15.2 |
| Auth API | djangorestframework-simplejwt | 5.3.1 |
| Tareas async | Celery | 5.4.0 |
| Scheduler | django-celery-beat | 2.6.0 |
| Resultados Celery | django-celery-results | 2.6.0 |
| Storage | Azure Blob Storage (azure-storage-blob) | — |
| Servidor prod | Gunicorn | — |
| Static files | Whitenoise | — |

### IA / ML actual
| Componente | Tecnología |
|---|---|
| LLM Provider | DeepSeek API (ya integrado, ver `test_deepseek.py`) |
| Procesamiento IA | `ingestas/procesamiento_ia.py` |
| Análisis de requerimientos | `mcp-deepseek-requerimientos/` (MCP server en TypeScript) |

### Data & Analytics
| Componente | Tecnología |
|---|---|
| Visualizaciones | Matplotlib 3.8 + Seaborn 0.13 |
| Procesamiento Excel | Pandas 2.2 + openpyxl 3.1 |
| PDFs | ReportLab 4.2 |
| Web scraping actual | Selenium + BeautifulSoup4 + Requests |
| Marketing data | Facebook Business SDK (Meta Ads API) |

### Infraestructura
| Componente | Servicio Azure |
|---|---|
| App hosting | Azure App Service |
| Base de datos | Azure SQL |
| File storage | Azure Blob Storage |
| Deploy config | `startup.sh`, `Procfile`, `.deployment`, `oryx-manifest.toml` |
| Variables de entorno | `webapp/.env` (via django-environ) |

---

## 3. ARQUITECTURA DE APLICACIONES DJANGO

El proyecto vive en `webapp/` como proyecto Django monolítico. Las apps instaladas son:

### Apps de Dominio Inmobiliario

**`propifai/`** — App principal. Portfolio propio de propiedades.
- Modelos: propiedades propias de la inmobiliaria
- Vistas: listados, detalle, dashboard de calidad de cartera
- Mapeo de ubicaciones: `mapeo_ubicaciones.py`, `mapeo_ubicaciones_propifai.json`
- Templates: `lista_propiedades_propify.html`, `dashboard_calidad_cartera.html`, `property_visits_dashboard.html`

**`ingestas/`** — Importación y normalización de propiedades externas (competencia).
- Modelo central: `PropiedadRaw` — propiedades scrapeadas de portales externos
- Procesamiento IA: `procesamiento_ia.py` — usa DeepSeek para enriquecer/validar datos
- Importación Excel: comando `importar_excel_propiedadraw`
- Migraciones: 12 migraciones (campo más reciente: `condicion_propiedad_verificada`)
- Templates: lista, detalle, editar, validar, procesar_ia

**`requerimientos/`** — CRM de demanda. Requerimientos de clientes buscando propiedades.
- Modelos: `RequerimientoRaw`, `Requerimiento`
- Fuentes: WhatsApp exports, Excel (Remax, red inmobiliaria propia)
- Analytics: `analytics.py` — análisis temporal de demanda
- Datos de ejemplo en: `requerimientos/data/`

**`matching/`** — Motor de matching oferta-demanda.
- Engine: `engine.py` — cruza requerimientos con propiedades disponibles
- Modos: individual y masivo
- Tiene serializers para API

**`acm/`** — Análisis Comparativo de Mercado.
- Vistas de análisis de precio por zona/tipo
- Templates: `acm_analisis.html`, `acm_analisis_compacto.html`

**`cuadrantizacion/`** — Sistema de segmentación geográfica.
- Jerarquía: País → Departamento → Provincia → Distrito → Zona → Subzona/Cuadrante
- Modelo `ZonaValor` con coordenadas
- Comandos: `calcular_precios_zonas`, `migrar_propiedades_valoracion`
- Vistas: mapa de zonas con heatmap, configurar jerarquía

**`market_analysis/`** — Dashboard de inteligencia de mercado.
- Heatmap de precios con Google Maps
- Dashboard de calidad de datos
- Charts con Matplotlib (`charts.py`)

### Apps de Infraestructura

**`colas/`** — Configuración de Celery.
- `celery.py` — app Celery
- `tasks.py`, `tareas_captura.py`, `tareas_descubrimiento.py`

**`captura/`** — Sistema de captura y monitoreo de URLs.
- Screenshot de páginas web (`captura_screenshot.py`)
- OCR y extracción de PDFs (`extractor_pdf.py`)
- Detección de cambios (`diff_engine.py`)
- Storage en Azure Blob (`azure_storage.py`)

**`semillas/`** — Fuentes web para scraping.
- Modelo `FuenteWeb` con categorías y estado activo
- Descubrimiento automático de nuevas URLs

**`api/`** — API REST pública.
- Versiones: `urls.py` (original) y `urls_mejoradas.py`
- Documentación: `API_DOCUMENTATION.md`, `ANDROID_IMPLEMENTATION_GUIDE.md`
- Serializers para propiedades y requerimientos

**`meta_ads/`** — Integración Meta Marketing API.
- Sync de campañas Facebook Ads
- Dashboard de rendimiento, análisis histórico
- Comando: `sync_meta_ads`
- Nota: hubo problemas de token vencido (ver `SOLUCION_TOKEN_META_VENCIDO.md`)

**`analisis_crm/`** — Dashboard CRM analytics.
- Lead tracking, pipeline intelligence
- Templates: `dashboard.html`, `lead_detail.html`, `analytics.html`
- ESTADO: en desarrollo activo

**`eventos/`** — Registro de eventos del sistema.
- Dashboard de eventos, detalle

### Configuración Central
- `settings.py` — settings principal
- `urls.py` — URL router principal
- `routers.py` — routers de BD (mssql)
- `asgi.py` / `wsgi.py`

---

## 4. ESTRUCTURA DE CARPETAS

```
Prometeo/                          ← Raíz del repositorio
├── webapp/                        ← Proyecto Django (AQUÍ VIVE TODO)
│   ├── manage.py
│   ├── settings.py
│   ├── urls.py
│   ├── requirements.txt
│   ├── .env                       ← Variables de entorno (NO commitear)
│   ├── Procfile                   ← Para Azure App Service
│   ├── startup.sh
│   ├── [apps Django]/             ← Ver sección 3
│   ├── templates/                 ← Templates globales
│   └── static/                   ← Static files globales
│
├── mcp-deepseek-requerimientos/   ← MCP Server TypeScript (análisis de requerimientos)
│   ├── src/index.ts               ← Servidor MCP principal
│   ├── src/index-simple.ts        ← Versión simplificada
│   └── build/                    ← Compilado JS
│
└── elgranextractor/               ← LEGACY/DUPLICADO — copias antiguas del proyecto
    └── webapp/                    ← NO usar esta carpeta, usar /webapp/ del root
```

> ⚠️ **IMPORTANTE PARA AGENTES:** El código activo está en `/webapp/` del root.
> La carpeta `/elgranextractor/webapp/` es una copia antigua. NO modificar.

---

## 5. CONVENCIONES Y PATRONES ESTABLECIDOS

### Reglas de código que SIEMPRE debes seguir

1. **Solo Django ORM** — Nunca SQL raw salvo que sea absolutamente imposible con ORM. Si necesitas SQL directo, documentar el motivo.

2. **Base de datos es Azure SQL (SQL Server)** — NO PostgreSQL. La sintaxis difiere. El driver es `mssql-django`. Evitar funciones PostgreSQL-only.

3. **Visualizaciones con Matplotlib** — Tema oscuro con background `#0d1117`. Mantener consistencia visual.

4. **Celery para tareas async** — Cualquier proceso que tarde más de 2 segundos va a una tarea Celery.

5. **Azure Blob Storage** — Para todos los archivos/imágenes. Ver patrón en `captura/azure_storage.py`.

6. **DRF para APIs** — Usar serializers. No devolver JSON crudo desde views Django.

7. **Variables de entorno** — Todo en `.env` via `django-environ`. Nunca hardcodear credenciales.

### Patrones de naming
- Apps: nombre en español descriptivo (`ingestas`, `requerimientos`, `cuadrantizacion`)
- Modelos: PascalCase en español (`PropiedadRaw`, `RequerimientoRaw`, `FuenteWeb`)
- Views: snake_case, sufijo por tipo (`lista_propiedades`, `detalle_propiedad`)
- Templates: `{app}/{nombre}.html`
- Comandos de management: infinitivo en español (`importar_excel_propiedadraw`)

---

## 6. CONTEXTO DE NEGOCIO (CRÍTICO PARA IA)

### El mercado inmobiliario de Arequipa
- **Distritos principales:** Cayma, Yanahuara, Cercado, Miraflores, José Luis Bustamante y Rivero, Sachaca, Cerro Colorado, Mariano Melgar, Paucarpata
- **Cayma tiene microzonas:** "Cayma alta" y "Cayma baja" tienen rangos de precio muy diferentes. No tratarlas igual.
- **Tipos de propiedad:** Departamento, Casa, Terreno, Local Comercial, Oficina
- **Condición:** Nueva, En planos, Usada, En construcción
- **Unidad de precio:** Soles (PEN) y Dólares (USD) — ambas monedas coexisten en el mercado
- **Precio/m²:** Varía enormemente por zona. No hacer comparaciones sin filtrar por zona.
- **Terrenos:** Usan área total, NO área construida. Los demás usan área construida. Esta distinción es CRÍTICA.

### Fuentes de datos del sistema
- **Propiedades propias (app `propifai`):** Portfolio de la inmobiliaria, datos de alta calidad
- **Propiedades competencia (app `ingestas` → `PropiedadRaw`):** Scrapeadas de Urbania, Adondevivir, Remax, etc.
- **Requerimientos (app `requerimientos`):** Clientes buscando propiedades — fuente: WhatsApp grupos inmobiliarios + Excel Remax
- **Meta Ads (app `meta_ads`):** Campañas Facebook/Instagram de la inmobiliaria

### Reglas de negocio críticas
1. Un "requerimiento" es la demanda de un cliente. Un "match" cruza requerimientos con propiedades disponibles.
2. El ACM (Análisis Comparativo de Mercado) compara propiedades similares en zona similar para estimar valor.
3. La cuadrantización divide Arequipa en zonas → subzonas para análisis granular de precios.
4. `es_propify = True` en modelos significa que la propiedad pertenece al portfolio propio.

---

## 7. FEATURES IMPLEMENTADAS (Estado actual)

| Feature | App | Estado | Notas |
|---|---|---|---|
| Listado y gestión de propiedades propias | `propifai` | ✅ Producción | |
| Importación de propiedades externas (Excel) | `ingestas` | ✅ Producción | |
| Procesamiento IA de propiedades | `ingestas` | ✅ Producción | Usa DeepSeek |
| CRM de requerimientos de clientes | `requerimientos` | ✅ Producción | |
| Motor de matching oferta-demanda | `matching` | ✅ Producción | Individual y masivo |
| ACM — Análisis Comparativo de Mercado | `acm` | ✅ Producción | |
| Heatmap de precios Google Maps | `market_analysis` | ✅ Producción | |
| Dashboard calidad de datos | `market_analysis` | ✅ Producción | |
| Segmentación geográfica (cuadrantización) | `cuadrantizacion` | ✅ Producción | |
| Captura y monitoreo de URLs | `captura` | ✅ Producción | |
| API REST para móvil/terceros | `api` | ✅ Producción | JWT auth |
| Meta Ads — Sync Facebook Campaigns | `meta_ads` | ✅ Producción | Token largo resuelto |
| Dashboard CRM analytics | `analisis_crm` | 🔄 En desarrollo | |
| MCP Server análisis requerimientos | `mcp-deepseek-requerimientos/` | ✅ Operativo | TypeScript |

---

## 8. PRÓXIMAS FEATURES A IMPLEMENTAR

### Prioridad ALTA (Fase A — IA Asistente)
- [ ] **pgvector / búsqueda semántica** — Requiere migrar o añadir PostgreSQL como segunda BD, o evaluar alternativa compatible con Azure SQL
- [ ] **RAG sobre propiedades** — Pipeline: embedding → vector search → DeepSeek response
- [ ] **Chat asistente interno** — Chatbot para búsqueda de propiedades por lenguaje natural
- [ ] **Memoria de sesión y usuario** — Redis para corto plazo, DB para largo plazo
- [ ] **Validación inteligente de datos** — Guardrails al ingresar propiedades

### Prioridad MEDIA (Fase B — Scraping inteligente)
- [ ] **Scraping robusto con Playwright** — Reemplazar Selenium actual
- [ ] **Pipeline de ingestión automática** — Celery Beat + scrapers → BD → embeddings
- [ ] **News intelligence** — Noticias inmobiliarias Arequipa (proyectos, leyes municipales)

### Prioridad BAJA (Fase C — API pública)
- [ ] **FastAPI microservicio** — Exponer capacidades IA como API independiente
- [ ] **Sistema de API Keys** — Multi-tenant, rate limiting, tiers
- [ ] **Documentación OpenAPI** — Para integración con HubSpot, Salesforce, etc.

---

## 9. DEUDA TÉCNICA CONOCIDA

### Crítica — Resolver antes de escalar
1. **Cientos de scripts sueltos en el root** — El directorio raíz tiene ~300+ archivos `test_*.py`, `check_*.py`, `verificar_*.py`, `debug_*.py` acumulados durante el desarrollo. Son scripts ad-hoc que deben ser:
   - Eliminados si ya no sirven
   - Movidos a `tests/` si son tests reales
   - Convertidos a comandos de management si son utilitarios

2. **Duplicación `elgranextractor/`** — La carpeta `/elgranextractor/webapp/` duplica `/webapp/`. Confirmar si es legacy o tiene algo útil, luego eliminar.

3. **Múltiples archivos HTML de prueba en root** — `heatmap_*.html`, `page*.html`, `temp*.html`, etc. Limpiar.

### Media — Resolver en próximas semanas
4. **`market_analysis` sin modelos propios** — Las migraciones están vacías (`__init__.py` solamente). Los datos vienen de otras apps. Evaluar si necesita modelos propios.

5. **`analisis_crm` sin migraciones** — App nueva, migraciones vacías. Definir modelo de leads antes de continuar.

6. **Dos versiones de API** — `api/urls.py` y `api/urls_mejoradas.py`. Consolidar en una sola.

7. **Templates duplicados** — Varios templates tienen versiones `_backup`, `_clonado`, `_debug`. Limpiar y dejar solo la versión final.

---

## 10. VARIABLES DE ENTORNO REQUERIDAS

> El agente NUNCA debe hardcodear estos valores. Siempre usar `os.environ` o `env()` de django-environ.

```bash
# Base de datos
DATABASE_URL=                  # Azure SQL connection string

# Django
SECRET_KEY=
DEBUG=False
ALLOWED_HOSTS=

# Azure Storage
AZURE_ACCOUNT_NAME=
AZURE_ACCOUNT_KEY=
AZURE_CONTAINER=

# DeepSeek API
DEEPSEEK_API_KEY=

# Google Maps
GOOGLE_MAPS_API_KEY=

# Meta (Facebook) Ads
META_ACCESS_TOKEN=             # Token largo (60 días)
META_APP_ID=
META_APP_SECRET=
META_AD_ACCOUNT_ID=

# Celery / Redis
CELERY_BROKER_URL=             # Redis URL
```

---

## 11. COMANDOS FRECUENTES

```bash
# Desarrollo local
cd webapp/
python manage.py runserver

# Migraciones
python manage.py makemigrations {app}
python manage.py migrate

# Celery worker
celery -A colas worker --loglevel=info

# Celery beat (scheduler)
celery -A colas beat --loglevel=info

# Importar propiedades desde Excel
python manage.py importar_excel_propiedadraw

# Importar requerimientos
python manage.py importar_requerimientos_excel

# Sync Meta Ads
python manage.py sync_meta_ads

# Calcular precios por zona
python manage.py calcular_precios_zonas
```

---

## 12. DECISIONES TÉCNICAS TOMADAS (Y POR QUÉ)

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Azure SQL como BD principal | PostgreSQL | La empresa ya tenía Azure; mssql-django funciona bien |
| DeepSeek como LLM | OpenAI GPT-4 | Costo/beneficio superior para español; ya integrado |
| Celery para async | Django Q, Huey | Ecosistema más maduro, mejor integración con Beat |
| Azure Blob para storage | S3, local | Consistencia con stack Azure existente |
| Django monolítico | Microservicios | Velocidad de desarrollo; equipo pequeño |
| Selenium para scraping | Scrapy | Necesidad de JS rendering; Playwright es la migración planeada |

---

## 13. LO QUE NO QUEREMOS HACER

1. **No romper producción** — Cualquier cambio en modelos existentes requiere migración probada.
2. **No agregar dependencias sin evaluar** — Cada nueva librería se añade al `requirements.txt` con versión fija.
3. **No SQL raw sin justificación** — El ORM cubre el 95% de los casos.
4. **No hardcodear valores de negocio** — Zonas, tipos de propiedad, rangos de precio van a BD o settings, no al código.
5. **No crear más scripts sueltos en root** — Cualquier script utilitario nuevo va como comando de management en la app correspondiente.
6. **No duplicar templates** — Un template, una versión. Si hay que refactorizar, se reemplaza.

---

## 14. INSTRUCCIONES PARA AGENTES IA

### Antes de implementar cualquier feature
1. Leer este documento completo
2. Identificar qué app Django es la más apropiada (o si hay que crear una nueva)
3. Verificar si ya existe algo similar en las apps actuales
4. Preguntar si la decisión de arquitectura no está clara

### Al crear código
- Seguir los patrones de naming de la sección 5
- Usar Azure SQL syntax (no PostgreSQL)
- Si creas un script de prueba, créalo como test en `{app}/tests.py`, no en el root
- Documentar decisiones no obvias con comentarios

### Al modificar modelos existentes
- Siempre crear migración
- Verificar que la migración funciona con Azure SQL (algunas operaciones difieren de PostgreSQL)
- No eliminar campos con datos en producción sin estrategia de migración

### Al agregar nuevas librerías
- Añadir a `requirements.txt` con versión específica
- Documentar para qué se usa en este archivo (sección stack)

---

*Última actualización: Abril 2026*
*Versión del documento: 1.0*
*Próxima revisión: Al completar analisis_crm dashboard*
