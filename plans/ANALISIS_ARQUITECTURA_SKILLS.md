# Análisis del Dashboard de Skills y Arquitectura del Sistema de Skills

> Proyecto: **Prometeo / Propifai** · App: `intelligence` · Documento de análisis técnico.
> Fecha: 2026-08-22 · Autores: análisis automatizado.

---

## 1. Dashboard de Skills — `GET /intelligence/skills/dashboard/`

### 1.1 Vista que lo sirve

| Campo | Valor |
|---|---|
| Vista | [`skills_dashboard_view()`](webapp/intelligence/views.py:3177) |
| Template | `intelligence/skills_dashboard.html` |
| Control de acceso | Autenticación por sesión (`get_authenticated_user`); sin sesión muestra dashboard público sin datos sensibles |
| URL | `/intelligence/skills/dashboard/` |

### 1.2 Qué muestra (fuentes reales)

| Sección | Fuente de datos | Descripción |
|---|---|---|
| **Listado de skills** | `SKILL_SYSTEM.list_available_skills()` | Todas las skills registradas con su schema (name, description, category, access_level, is_active, parameters_schema) |
| **KPI: ejecuciones totales** | `SELECT COUNT(*) FROM intelligence_skill_execution` | Total histórico de ejecuciones |
| **KPI: ejecuciones últimas 24 h** | `... WHERE executed_at >= now - 24h` | Ejecuciones del día |
| **KPI: éxito / error / cacheadas** | `... WHERE status='success'/'error'`, `cached=1` | Conteos por estado |
| **Tasa de éxito** | `success/total * 100` | Porcentaje de éxito real |
| **Latencia promedio** | `AVG(latency_ms) WHERE status='success'` | Latencia media (ms) |
| **Cache hit rate** | `cached/total * 100` | Porcentaje de respuestas cacheadas |
| **Tabla por skill** | `GROUP BY skill_name` (count + avg latency) | Ejecuciones y latencia por skill |
| **Gráfico por hora** | 24 consultas por hora a `intelligence_skill_execution` | Barras de ejecuciones en las últimas 24 h (hora local `America/Lima`) |
| **Ejecuciones recientes** | `SELECT TOP 20 ... ORDER BY executed_at DESC` | Últimas 20 ejecuciones con estado, latencia, cache, error y fecha |

> Nota: el dashboard consulta la tabla `intelligence_skill_execution` con **SQL directo** (compatible SQL Server / mssql-django).

### 1.3 Comportamiento destacado

- El dashboard intenta **redescubrir skills** al cargar (`DynamicRegistry().discover_skills(...)`), aunque en el `SkillRegistry` actual ese método es un **no-op** (el registro es explícito).
- La escala del gráfico por hora se ajusta para que barras pequeñas sean visibles (`scale_max` y umbral mínimo de altura).
- Los datos de ejecución persisten en la tabla `intelligence_skill_execution` (modelo `SkillExecution`).

---

## 2. Arquitectura del Sistema de Skills

### 2.1 Componentes principales

```
┌────────────────────────────────────────────────────────────────────┐
│                        VISTAS / API                                │
│  skills_dashboard_view · skill_detail_view · skills_create/edit    │
│  toggle_skill · urls.py (intelligence/urls.py)                     │
└───────────────┬────────────────────────────────────────────────────┘
                │
┌───────────────▼────────────────────────────────────────────────────┐
│                   SKILL_SYSTEM (SkillOrchestrator)                 │
│  orchestrator.py — get_skill_info, find_best_skill, list, exec     │
└───────────────┬────────────────────────────────────────────────────┘
                │ delega en
┌───────────────▼────────────────────────────────────────────────────┐
│                     SkillRegistry (singleton)                      │
│  registry.py — register, find_best_skill, get_by_name,            │
│  get_skill_info, list_available, list_all, list_skills,           │
│  search_skills, activate, deactivate, get_stats, clear            │
│  + SemanticSkillRouter (embedding E5) para selección               │
└───────────────┬────────────────────────────────────────────────────┘
                │ contiene / registra
┌───────────────▼────────────────────────────────────────────────────┐
│                       BaseSkill (abstracta)                        │
│  base.py — name, description, category, access_level, is_active,  │
│  parameters_schema, required_domain, required_collection,         │
│  accepts_previous_results · execute() · validate_params()         │
│  · get_schema()                                                    │
└───────────────┬────────────────────────────────────────────────────┘
                │ instancias de skills concretas
┌───────────────▼────────────────────────────────────────────────────┐
│  Skills de negocio  ·  Skills de scraping  ·  Skills de ejemplo    │
│  intelligence/skills/…                                            │
│  (busqueda_propiedades, acm_analisis, scraper_remax, …)           │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 Clase base — `BaseSkill` ([`intelligence/skills/base.py`](webapp/intelligence/skills/base.py:91))

**Atributos de clase** (toda skill los define):

| Atributo | Tipo | Descripción |
|---|---|---|
| `name` | `str` | Identificador único en snake_case (obligatorio) |
| `description` | `str` | Descripción en lenguaje natural para que el agente elija la skill (obligatorio) |
| `category` | `str` | `busqueda` · `crm` · `reporte` · `notificacion` · `template` · `custom` |
| `access_level` | `int` | Nivel mínimo de acceso (1–5) |
| `is_active` | `bool` | Disponible para el agente (default `True`) |
| `parameters_schema` | `dict` | Schema de parámetros aceptados |
| `required_domain` | `str?` | Dominio requerido (ej. `legal`, `marketing`, `ti`, `gerencia`) |
| `required_collection` | `str?` | Colección RAG requerida (ej. `normativas_legales`) |
| `accepts_previous_results` | `bool` | Acepta resultados de una skill previa (multi-skill, SPEC v2.1) |

**Validación automática** (`__init_subclass__`): obliga `name` y `description` no vacíos, avisa si `category` no es estándar y valida que `parameters_schema` sea dict.

**Métodos abstractos**:
- `execute(params, context) -> SkillResult`
- `validate_params(params) -> bool`

**Método concreto**: `get_schema()` → dict con `name`, `description`, `category`, `access_level`, `is_active`, `parameters_schema` (y campos extendidos si existen).

### 2.3 Resultado estandarizado — `SkillResult` ([`base.py`](webapp/intelligence/skills/base.py:21))

Dataclass: `success`, `data`, `message`, `metadata`, `skill_name`.
Helpers: `SkillResult.ok(...)`, `SkillResult.error(...)`, y alias de compatibilidad `error_message` y `SkillResult.from_error(...)` (para el `SkillResult` LEGACY).

### 2.4 Registro — `SkillRegistry` ([`registry.py`](webapp/intelligence/skills/registry.py:104))

- **Singleton** (`__new__` + `_instance`).
- Almacena `_skills: dict[name → instancia]` y `_skill_classes: dict[name → clase]`.
- **Registro**: `register(skill_class)` — valida que herede de `BaseSkill`, lo instancia y lo guarda. En producción el registro es **explícito** en `apps.py` al iniciar Django (se registran las ~40 skills de negocio + 5 scrapi + 20 nuevas multi-rol).
- **Selección** (`find_best_skill`):
  1. **Primario**: `SemanticSkillRouter` con embeddings **E5-large** (`get_router(threshold=0.45)`).
  2. **Fallback**: coincidencia por keywords/dominio.
- **Info/metadata**: `get_by_name`, `get_skill_info` (schema de una skill), `list_available`, `list_all`, `list_skills` (alias), `search_skills`, `get_stats`.
- **Activación**: `activate` / `deactivate`.
- `discover_skills()` es un **no-op** (compatibilidad): el registro ya no es automático.

> **Bug corregido en esta sesión**: el método `get_skill_info` **no existía** en `SkillRegistry` aunque `orchestrator.py:487` y varias vistas lo llamaban → `AttributeError`. Se agregó (retorna `skill.get_schema()` o `None`). **Cambio pendiente de push.**

### 2.5 Orquestador — `SkillOrchestrator` (`orchestrator.py`)

Expone la API de alto nivel usada por las vistas y agentes: `get_skill_info`, `find_best_skill`, listado, etc. Delega la lógica en el `SkillRegistry` (accedido como `SKILL_SYSTEM`).

### 2.6 Agentes que usan skills

- `AgentRegistry` + `BaseAgent` (`intelligence/agents/`).
- Agentes registrados al inicio: `agente_propiedades`, `agente_mercado`, `agente_requerimientos`, `agente_inteligencia_leads`.
- Cada agente tiene un conjunto de skills (dominio + nivel).

### 2.7 Persistencia de ejecuciones

- Tabla **`intelligence_skill_execution`** (modelo `SkillExecution`): registra `skill_name`, `status`, `latency_ms`, `cached`, `error_message`, `executed_at`.
- La usan el dashboard (KPIs, gráficos, tabla) y los agentes para tracking.

### 2.8 Ciclo de vida de una skill

1. **Definir**: clase que hereda de `BaseSkill`, con `name`, `description`, `category`, `access_level`, `parameters_schema`, e implementa `execute()` y `validate_params()`.
2. **Registrar**: en `apps.py` (al iniciar Django) o dinámicamente con `registry.register(...)`.
3. **Seleccionar**: el agente/orquestador elige la mejor skill vía `find_best_skill` (router semántico → keywords).
4. **Ejecutar**: `skill.execute(params, context)` → `SkillResult`.
5. **Registrar**: se persiste la ejecución en `intelligence_skill_execution` (estado, latencia, cache).
6. **Formatear**: el agente usa el `SkillResult` para responder de forma consistente.

---

## 3. Skills registradas (inventario observado al inicio de Django)

| Skill | Categoría | Nivel |
|---|---|---|
| `busqueda_propiedades` | busqueda | 1 |
| `acm_analisis` | reporte | 1 |
| `reporte_precios_zona` | reporte | 1 |
| `matching_oferta_demanda` | crm | 1 |
| `matching_hibrido` | crm | 1 |
| `busqueda_exacta` | busqueda | 1 |
| `formatear_propiedades` | busqueda | 1 |
| `clasificar_intencion_whatsapp` | crm | 1 |
| `analizar_conversacion_lead` | crm | 3 |
| `metricas_globales` | reporte | 5 |
| `reporte_ventas` | reporte | 5 |
| `analisis_rendimiento` | reporte | 5 |
| `consultar_normativa` | busqueda | 1 |
| `revisar_contrato` | custom | 3 |
| `aspectos_legales` | busqueda | 1 |
| `campanas_activas` | reporte | 3 |
| `leads_generados` | reporte | 3 |
| `metricas_marketing` | reporte | 3 |
| `mis_propiedades` | busqueda | 1 |
| `mis_requerimientos` | crm | 1 |
| `mis_matches` | crm | 1 |
| `portafolio_agente` | busqueda | 1 |
| `analizar_oportunidad` | reporte | 1 |
| `equipo_a_cargo` | reporte | 3 |
| `desempeno_agentes` | reporte | 3 |
| `reporte_equipo` | reporte | 3 |
| `logs_sistema` | reporte | 4 |
| `errores_recientes` | reporte | 4 |
| `estado_servicios` | reporte | 4 |
| `scraper_remax` | custom | 1 |
| `scraper_adondevivir` | custom | 1 |
| `scraper_properati` | custom | 1 |
| `scraper_urbania` | custom | 1 |
| `scraper_orchestrator` | custom | 1 |
| `informacion_inicial_propiedad` | busqueda | 1 |
| `suma`, `resta`, `multiplicacion`, `division`, `potencia`, `raiz_cuadrada`, `estadisticas_basicas`, `contar_palabras`, `filtrar_lista`, `ordenar_lista`, `resumir_texto` | ejemplos | 1 |

> Las skills de la categoría `ejemplos` generan warnings al inicio (categoría no estándar) — ver deuda técnica.

---

## 4. Vistas / endpoints del módulo skills

| URL | Vista | Función |
|---|---|---|
| `/intelligence/skills/dashboard/` | `skills_dashboard_view` | KPIs, tabla y charts |
| `/intelligence/skills/<name>/detail/` | `skill_detail_view` | Detalle, métricas, ejecución e historial |
| `/intelligence/skills/create/` | (creación) | Crear skill nueva (archivo .py) |
| (edit / delete / toggle) | varias | Editar, eliminar, activar/desactivar skills |

---

## 5. Observaciones y deuda técnica

1. **`get_skill_info` faltante (corregido localmente, sin push)**: la vista de detalle daba `AttributeError`; el método ya se agregó a `SkillRegistry`.
2. **Registro explícito vs descubrimiento**: `discover_skills()` es no-op; las skills nuevas deben registrarse en `apps.py` o dinámicamente — si se olvida, no aparecen.
3. **Categoría `ejemplos` no estándar**: las skills de ejemplo (`suma`, etc.) generan warnings; convendría separarlas de producción.
4. **SQL directo en el dashboard**: las consultas a `intelligence_skill_execution` son raw SQL (necesario por SQL Server) — mantener compatibilidad mssql-django.
5. **Dos mecanismos de selección**: router semántico (embeddings) + keywords; el umbral es 0.45. Monitorear falsos positivos.
6. **Duplicación de carpetas**: `elgranextractor/webapp/intelligence` es copia legacy; el código activo está en `webapp/intelligence`.
