# Resumen del Contexto de Sesión

## Proyecto Actual
- **Nombre**: Prometeo (Propifai)
- **Tipo**: PropTech SaaS - Plataforma de gestión e inteligencia inmobiliaria
- **Ubicación**: Arequipa, Perú (con visión de expansión a Latinoamérica)
- **Metodología**: Lean Startup - velocidad de iteración sobre perfección
- **Etapa**: Producción activa + desarrollo continuo

## Stack Tecnológico
### Backend
- **Framework**: Django 5.0.6
- **Base de datos**: Azure SQL (SQL Server) con driver mssql-django
- **API REST**: Django REST Framework 3.15.2
- **Autenticación**: JWT (djangorestframework-simplejwt)
- **Tareas async**: Celery 5.4.0 + Redis
- **Storage**: Azure Blob Storage
- **Servidor producción**: Gunicorn + Whitenoise

### IA/ML
- **LLM Provider**: DeepSeek API (ya integrado)
- **Procesamiento IA**: `ingestas/procesamiento_ia.py`
- **MCP Server**: `mcp-deepseek-requerimientos/` (TypeScript para análisis de requerimientos)

### Data & Analytics
- **Visualizaciones**: Matplotlib 3.8 + Seaborn 0.13
- **Procesamiento Excel**: Pandas 2.2 + openpyxl 3.1
- **PDFs**: ReportLab 4.2
- **Web scraping**: Selenium + BeautifulSoup4 + Requests (migración planeada a Playwright)

### Infraestructura Azure
- App Service, Azure SQL, Blob Storage
- Configuración: `startup.sh`, `Procfile`, `.deployment`, `oryx-manifest.toml`

## Arquitectura Django (webapp/)
### Apps de Dominio Inmobiliario
1. **propifai/**: Portfolio propio de propiedades
2. **ingestas/**: Importación y normalización de propiedades externas (PropiedadRaw)
3. **requerimientos/**: CRM de demanda (RequerimientoRaw, Requerimiento)
4. **matching/**: Motor de matching oferta-demanda
5. **acm/**: Análisis Comparativo de Mercado
6. **cuadrantizacion/**: Segmentación geográfica (País → Departamento → Provincia → Distrito → Zona → Subzona)
7. **market_analysis/**: Dashboard de inteligencia de mercado con heatmaps

### Apps de Infraestructura
1. **colas/**: Configuración Celery
2. **captura/**: Sistema de captura y monitoreo de URLs (screenshots, OCR, detección de cambios)
3. **semillas/**: Fuentes web para scraping
4. **api/**: API REST pública con JWT auth
5. **meta_ads/**: Integración Meta Marketing API (Facebook Ads)
6. **analisis_crm/**: Dashboard CRM analytics (en desarrollo)
7. **eventos/**: Registro de eventos del sistema

## Contexto de Negocio Crítico
### Mercado Inmobiliario de Arequipa
- **Distritos principales**: Cayma, Yanahuara, Cercado, Miraflores, JLBR, Sachaca, Cerro Colorado, Mariano Melgar, Paucarpata
- **Cayma tiene microzonas**: "Cayma alta" y "Cayma baja" con rangos de precio diferentes
- **Tipos de propiedad**: Departamento, Casa, Terreno, Local Comercial, Oficina
- **Condición**: Nueva, En planos, Usada, En construcción
- **Monedas**: Soles (PEN) y Dólares (USD) coexisten
- **Terrenos**: Usan área total (NO área construida) - distinción crítica

### Fuentes de Datos
1. **Propiedades propias** (app `propifai`): Portfolio de la inmobiliaria
2. **Propiedades competencia** (app `ingestas` → `PropiedadRaw`): Scrapeadas de Urbania, Adondevivir, Remax, etc.
3. **Requerimientos** (app `requerimientos`): Clientes buscando propiedades (WhatsApp grupos + Excel Remax)
4. **Meta Ads** (app `meta_ads`): Campañas Facebook/Instagram

### Reglas de Negocio
- `es_propify = True` en modelos significa propiedad del portfolio propio
- Un "requerimiento" es la demanda de un cliente
- El ACM compara propiedades similares en zona similar para estimar valor
- La cuadrantización divide Arequipa en zonas → subzonas para análisis granular

## Estado Actual del Proyecto
### Features Implementadas (✅ Producción)
- Listado y gestión de propiedades propias
- Importación de propiedades externas (Excel)
- Procesamiento IA de propiedades (DeepSeek)
- CRM de requerimientos de clientes
- Motor de matching oferta-demanda
- ACM - Análisis Comparativo de Mercado
- Heatmap de precios Google Maps
- Dashboard calidad de datos
- Segmentación geográfica (cuadrantización)
- Captura y monitoreo de URLs
- API REST para móvil/terceros
- Meta Ads - Sync Facebook Campaigns
- MCP Server análisis requerimientos

### Próximas Features (Prioridad)
- **Fase A - IA Asistente**: pgvector/búsqueda semántica, RAG sobre propiedades, chat asistente interno
- **Fase B - Scraping inteligente**: Playwright, pipeline de ingestión automática
- **Fase C - API pública**: FastAPI microservicio, sistema de API Keys

### Deuda Técnica Conocida
1. **Cientos de scripts sueltos en root**: ~300+ archivos `test_*.py`, `check_*.py`, etc. (necesitan organización)
2. **Duplicación `elgranextractor/`**: Carpeta duplica `/webapp/` (legacy)
3. **Múltiples archivos HTML de prueba en root**: `heatmap_*.html`, `page*.html`, etc.
4. **`market_analysis` sin modelos propios**: Migraciones vacías
5. **`analisis_crm` sin migraciones**: App nueva necesita modelos
6. **Dos versiones de API**: `api/urls.py` y `api/urls_mejoradas.py` (consolidar)
7. **Templates duplicados**: Versiones `_backup`, `_clonado`, `_debug`

## Convenciones y Patrones Establecidos
### Reglas de Código
1. **Solo Django ORM** - Evitar SQL raw salvo imposible
2. **Azure SQL (SQL Server)** - NO PostgreSQL, sintaxis diferente
3. **Visualizaciones con Matplotlib** - Tema oscuro background `#0d1117`
4. **Celery para tareas async** - Cualquier proceso >2 segundos va a Celery
5. **Azure Blob Storage** - Para todos los archivos/imágenes
6. **DRF para APIs** - Usar serializers, no JSON crudo
7. **Variables de entorno** - Todo en `.env` via django-environ

### Patrones de Naming
- **Apps**: nombre en español descriptivo (`ingestas`, `requerimientos`, `cuadrantizacion`)
- **Modelos**: PascalCase en español (`PropiedadRaw`, `RequerimientoRaw`, `FuenteWeb`)
- **Views**: snake_case, sufijo por tipo (`lista_propiedades`, `detalle_propiedad`)
- **Templates**: `{app}/{nombre}.html`
- **Comandos management**: infinitivo en español (`importar_excel_propiedadraw`)

## Variables de Entorno Requeridas
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

## Comandos Frecuentes
```bash
# Desarrollo local
cd webapp/
python manage.py runserver

# Migraciones
python manage.py makemigrations {app}
python manage.py migrate

# Celery worker
celery -A colas worker --loglevel=info

# Importar propiedades desde Excel
python manage.py importar_excel_propiedadraw

# Importar requerimientos
python manage.py importar_requerimientos_excel

# Sync Meta Ads
python manage.py sync_meta_ads

# Calcular precios por zona
python manage.py calcular_precios_zonas
```

## Decisiones Técnicas Tomadas
| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Azure SQL como BD principal | PostgreSQL | La empresa ya tenía Azure; mssql-django funciona bien |
| DeepSeek como LLM | OpenAI GPT-4 | Costo/beneficio superior para español; ya integrado |
| Celery para async | Django Q, Huey | Ecosistema más maduro, mejor integración con Beat |
| Azure Blob para storage | S3, local | Consistencia con stack Azure existente |
| Django monolítico | Microservicios | Velocidad de desarrollo; equipo pequeño |
| Selenium para scraping | Scrapy | Necesidad de JS rendering; Playwright es la migración planeada |

## Lo que NO queremos hacer
1. **No romper producción** - Cambios en modelos requieren migración probada
2. **No agregar dependencias sin evaluar** - Librerías con versión fija en requirements.txt
3. **No SQL raw sin justificación** - ORM cubre el 95% de los casos
4. **No hardcodear valores de negocio** - Zonas, tipos de propiedad van a BD o settings
5. **No crear más scripts sueltos en root** - Scripts utilitarios nuevos van como comandos de management
6. **No duplicar templates** - Un template, una versión

## Trabajo Realizado en esta Sesión
1. **Generación de estructura completa**: Creación de `arbol_completo.md` con árbol jerárquico de todo el proyecto (1870 líneas)
2. **Exclusión de entornos**: Se excluyeron `.venv` y `.vscode` como solicitado
3. **Inclusión completa**: Todos los archivos de `webapp/` incluyendo templates HTML, views, models, migrations, static files
4. **Documentación**: Archivo `estructura_proyecto.md` con resumen estructurado

## Archivos Relevantes Creados
- `estructura_proyecto.md`: Estructura resumida del proyecto
- `arbol_completo.md`: Árbol completo de archivos y carpetas
- `generar_arbol.py`: Script Python para generar el árbol
- `resumen_contexto_sesion.md`: Este resumen

## Modo Actual
- **Modo**: 💻 Code
- **Directorio de trabajo**: `d:/proyectos/prometeo`
- **Sistema**: Windows 11, shell cmd.exe
- **Idioma**: Español (según preferencia del usuario)