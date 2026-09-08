# Análisis del Módulo de Scraping — Dashboard `/ingestas/scraping/dashboard/`

> Documento técnico generado a partir del código (rama `main`, revisión `755ba0b8`).
> Alcance: arquitectura, lógica, estructura, skills por portal, funciones, última implementación y capítulo de campos nuevos para la línea de tiempo de m² por mes y por área.

---

## 1. Resumen del módulo

El módulo de scraping captura propiedades publicadas en portales inmobiliarios (Remax, Adondevivir, Properati, Urbania y Facebook Marketplace) usando un navegador automatizado **Camoufox** (perfiles persistentes por portal en `webapp/camoufox_session*`), estandariza los datos y los guarda en la tabla **`propiedades_competencia`** mediante *upsert* por `(fuente, id_origen)`.

El sistema está compuesto por:

1. **UI de control** (dashboard con terminal en vivo, tabla y controles start/pause/resume/stop).
2. **Modelo de trabajos** (`ScrapingJob`, `EjecucionPortal`, `ScrapingLog`, `PropiedadesCompetencia`).
3. **Motor de ejecución** (`colas/scraping_tasks.py`) que despacha jobs por portal en un hilo local, Celery o vía *watchdog*.
4. **Skills por portal** (`intelligence/skills/scrapi/*`) — cada portal es una `BaseSkill` ejecutable.
5. **Ciclo de vida de publicaciones** (`ingestas/lifecycle.py`) para detectar altas, ausencias y retiros.

---

## 2. Arquitectura y flujo de datos (visión general)

```text
+------------------+     POST /scraping/control/ (start)
|  ScrapingControl |
+--------+---------+
         | crea ScrapingJob (estado='idle', execution_token=NULL)
         v
+------------------+  _launch_scraping_job(job_id)
|  Modo ejecución  |  -> 'thread' (default) | 'celery' | 'watchdog'
+--------+---------+
         v
+---------------------------+  _run_scraping(job_id)
| colas/scraping_tasks.py   |  claim CAS idle->running (execution_token)
|  por cada portal:         |  heartbeat (log de actividad) para no ser
|  - start_or_resume_...    |  marcado como huérfano
|  - _instanciar_skill      |
|  - skill.execute(...)     |
|  - reportar_progreso(...) |
|  - finalize/fail portal   |
+--------+------------------+
         |
         v  (dentro de cada scraper-skill)
+---------------------------+   db_utils.guardar_propiedades()
| Camoufox navega + extrae  |   upsert en PropiedadesCompetencia
| -> estandariza_lote       |   (fuente, id_origen) + campos lifecycle
+--------+------------------+
         |
         v
+----------------------------+
| propiedades_competencia    |  (datos vigentes por portal)
| scraping_jobs              |  (estado/progreso/contadores)
| scraping_ejecuciones_portal|  (una ejecución confiable por portal/job)
| scraping_logs              |  (terminal SSE del dashboard)
+----------------------------+
```

**Flujo del usuario en el dashboard:**
1. Abre `/ingestas/scraping/dashboard/` (HTML con terminal + tabla).
2. Pulsa **Iniciar** y elige portales → `POST /scraping/control/` (acción `start`).
3. El navegador abre una conexión SSE a `/scraping/stream/<job_id>/` que recibe los `ScrapingLog` en tiempo real.
4. Cada 2s consulta `/scraping/status/<job_id>/` para progreso/contadores.

---

## 3. Estructura de archivos

| Archivo | Rol |
|---|---|
| `webapp/ingestas/urls.py` | Rutas `/ingestas/scraping/*` |
| `webapp/ingestas/views.py` | Vistas del dashboard, control, stream, status, tabla, historial + helpers |
| `webapp/ingestas/models.py` | `ScrapingJob`, `EjecucionPortal`, `ScrapingLog`, `PropiedadesCompetencia`, `PropiedadRaw` |
| `webapp/ingestas/lifecycle.py` | Control del ciclo de vida de publicaciones |
| `webapp/ingestas/management/commands/scraping_watchdog.py` | Recuperación de jobs huérfanos entre instancias |
| `webapp/colas/scraping_tasks.py` | Motor principal (hilo/Celery), orquestación por portal |
| `webapp/intelligence/skills/scrapi/scraper_orchestrator.py` | Skill orquestadora que enruta al portal |
| `webapp/intelligence/skills/scrapi/scraper_remax.py` | Skill Remax |
| `webapp/intelligence/skills/scrapi/scraper_adondevivir.py` | Skill Adondevivir |
| `webapp/intelligence/skills/scrapi/scraper_properati.py` | Skill Properati |
| `webapp/intelligence/skills/scrapi/scraper_urbania.py` | Skill Urbania |
| `webapp/intelligence/skills/scrapi/scraper_facebook_marketplace.py` | Skill Facebook Marketplace |
| `webapp/intelligence/skills/scrapi/db_utils.py` | `guardar_propiedades()` y `limpiar_fuente()` |
| `webapp/templates/ingestas/scraping_dashboard.html` | Template principal del dashboard |
| `webapp/templates/ingestas/scraping_tabla.html` | Tabla de propiedades (fragmento) |
| `webapp/intelligence/migrations/*` | Migraciones de la app intelligence (registro de skills) |
| `webapp/ingestas/migrations/0014_*` `0015_*` `0016_*` | Migraciones de trabajos, logs, ejecuciones y ciclo de vida |

---

## 4. Modelo de datos

### 4.1 `ScrapingJob` → tabla `scraping_jobs`
Registra un *trabajo* de scraping (puede agrupar varios portales).

| Campo | Tipo | Notas |
|---|---|---|
| `estado` | CharField(20) | `idle, running, paused, stopped, completed, error` |
| `execution_token` | UUID (nullable, indexado) | Claim exclusivo del ejecutor (evita doble ejecución) |
| `portal_actual` | CharField(50) | Portal que se está ejecutando |
| `progreso` | Integer | 0–100 global |
| `total_propiedades` | Integer | Detectadas |
| `procesadas` | Integer | Procesadas |
| `nuevas` / `actualizadas` / `errores` | Integer | Contadores acumulados |
| `parametros` | JSONField | `portales`, `execution_scope`, `execution_host`, `checkpoints`, `resume_item_ids`, `lifecycle_runs`, `resultados_por_portal` |
| `mensaje_error` | Text | Último error |
| `iniciado_en` / `completado_en` / `creado_en` | DateTime | |

### 4.2 `EjecucionPortal` → tabla `scraping_ejecuciones_portal`
Una *ejecución confiable por portal* (la unidad que detecta altas/ausencias/retiros).

| Campo | Notas |
|---|---|
| `token` | UUID único (reutilizable al reanudar el mismo job) |
| `job` | FK → `ScrapingJob` |
| `portal` | CharField(50), indexado |
| `estado` | `running, completed, incomplete, error` |
| `es_confiable` | Bool — solo las confiables se usan como referencia |
| `es_linea_base` | Bool — primera ejecución completa del portal |
| `propiedades_vistas` | Nº de propiedades vistas en esa ejecución |
| `posibles_retiradas` / `retiros_confirmados` | Conteos de ciclo de vida |
| `motivo_no_confiable` | Razón de cobertura insuficiente |
| `iniciado_en` / `completado_en` | |

### 4.3 `ScrapingLog` → tabla `scraping_logs`
Líneas del "terminal" en vivo del dashboard (SSE).

`job` FK, `nivel` (`info/warning/error`), `mensaje`, `portal`, `propiedad_id`, `timestamp`.

### 4.4 `PropiedadesCompetencia` → tabla `propiedades_competencia`
Propiedades vigentes scrapeadas (upsert por `fuente`+`id_origen`).

- **Identificación:** `fuente`, `id_origen`, `fecha_extraccion`, `url`, `titulo`.
- **Datos:** `tipo_inmueble`, `tipo_operacion`, `precio_soles`, `precio_usd`, `dormitorios`, `banos`, `estacionamientos`, `distrito`, `provincia`, `departamento`, `direccion_texto`, `latitud`, `longitud`, `descripcion`, `amenities`, `imagen_url`, `antiguedad_anios`, `agencia_agente`.
- **Ciclo de vida (última implementación):**
  `estado_publicacion`, `primera_vez_vista`, `ultima_vez_vista`, `fecha_primera_ausencia`, `fecha_retiro_confirmado`, `ausencias_consecutivas`, `ultima_ejecucion_vista` (FK → `EjecucionPortal`).
- **QA:** `datos_crudos` (JSON raw).
- `creado_en` / `actualizado_en`.

> Nota: `PropiedadRaw` (`propiedades_competencia` antiguo de Excel) es el modelo de importación por Excel; el scraping moderno escribe en `PropiedadesCompetencia`.

---

## 5. Dashboard web — vistas y funciones

### 5.1 Rutas (`webapp/ingestas/urls.py:30-37`)

| Ruta | Vista | Función |
|---|---|---|
| `/ingestas/scraping/dashboard/` | `ScrapingDashboardView` | HTML principal |
| `/ingestas/scraping/control/` | `ScrapingControlView` | `start/pause/resume/stop` |
| `/ingestas/scraping/stream/<job_id>/` | `ScrapingStreamView` | SSE logs en vivo |
| `/ingestas/scraping/status/<job_id>/` | `ScrapingStatusView` | JSON estado/progreso |
| `/ingestas/scraping/propiedades/` | `ScrapingPropiedadesView` | Tabla filtrable/paginada |
| `/ingestas/scraping/historial/` | `ScrapingHistorialView` | Historial de jobs |
| `/ingestas/scraping/test-import/` | `test_camoufox_import` | Prueba de import de Camoufox |

### 5.2 Helpers de módulo (`ingestas/views.py`)

- **`_decorate_scraping_job(job)`** (1666): añade campos de presentación (`origen_display`, `detectadas_display`, `estado_display`, `portales_detalle`). Si terminó `completed` sin resultados, lo muestra como error.
- **`_terminate_scraping_browsers()`** (1706): mata procesos `camoufox.exe` de perfiles `camoufox_session*` (PowerShell en Windows) y borra locks (`parent.lock`, `Singleton*`…). Devuelve cuántos mató.
- **`_reconcile_stale_scraping_jobs()`** (1773): marca como `error` jobs `running/paused/idle` sin logs recientes (`SCRAPING_STALE_AFTER_SECONDS`), limpiando `execution_token`.
- **`_launch_scraping_job(job_id)`** (1812): despacha sin bloquear la petición:
  - `SCRAPING_EXECUTION_MODE=celery` → `scraping_task.apply_async(job_id)`.
  - `watchdog` → devuelve sin lanzar (lo toma el worker watchdog).
  - default → hilo daemon local `scraping_task_run(job_id)`.
- **`_acquire_scraping_start_lock()`** (1844): en SQL Server usa `sp_getapplock('propifai:scraping:start')` para serializar el inicio entre instancias de Azure.

### 5.3 `ScrapingDashboardView` (1863)
`get_context_data()`:
- llama `_reconcile_stale_scraping_jobs()`;
- obtiene el último job y lo decora;
- estadísticas por portal (`PropiedadesCompetencia.values('fuente').annotate(total=Count)`);
- últimos 10 jobs decorados.
Contexto: `ultimo_job`, `stats_por_portal`, `total_propiedades`, `jobs_recientes`.

### 5.4 `ScrapingControlView` (1902, `csrf_exempt`)
`post(request)` según `action`:
- **`start`**: reconciliar huérfanos → lock de inicio → si hay job activo devuelve `409` → `_terminate_scraping_browsers()` → determina `execution_scope` (`local_interactive` solo si Windows y `facebook_marketplace`) → crea `ScrapingJob(estado='idle')` con `parametros{portales, execution_scope, execution_host}` → `_launch_scraping_job`. JSON: `{success, job_id, execution_mode, stale_browsers_terminated}`.
- **`pause`**: `running → paused`.
- **`resume`**: si `paused → running`; si `error/stopped` → termina browsers, vuelve a `idle`, y relanza desde checkpoints.
- **`stop`**: estado activo → `stopped`, token limpio, `_terminate_scraping_browsers()`.

### 5.5 `ScrapingStreamView` (2061)
Endpoint **SSE (EventSource)**: transmite `ScrapingLog` del job en vivo (mantiene conexión con heartbeat).

### 5.6 `ScrapingStatusView` (2119)
JSON con estado actual del job (progreso, contadores, portal).

### 5.7 `ScrapingPropiedadesView` (2158)
`ListView` filtrable y paginada de `PropiedadesCompetencia`.

### 5.8 `ScrapingHistorialView` (2216)
Historial de trabajos ejecutados.

### 5.9 Templates
- `webapp/templates/ingestas/scraping_dashboard.html` — layout + terminal + controles.
- `webapp/templates/ingestas/scraping_tabla.html` — tabla de resultados (parcial).

---

## 6. Motor de ejecución — `colas/scraping_tasks.py`

Funciones y su responsabilidad:

| Función | Línea | Rol |
|---|---|---|
| `_keep_windows_awake(function)` | 26 | Decorador: evita suspensión/hibernación en Windows mientras corre el scraping |
| `_error_camoufox_no_reintentable(resultado)` | 73 | Detecta errores de Camoufox que **no** deben reintentarse |
| `_mensaje_error_camoufox_no_reintentable(resultado)` | 90 | Mensaje para esos errores |
| `_resultado_portal_valido(resultado)` | 110 | Valida que el resultado de la skill tenga propiedades |
| `_instanciar_skill(portal)` | 122 | Mapea portal → clase de skill scrapi |
| `_actualizar_contadores(...)` | 146 | Suma contadores al job |
| `_registrar_resultado_portal(...)` | 185 | Guarda `resultados_por_portal` en `job.parametros` |
| `_crear_log(job, nivel, mensaje, portal, propiedad_id)` | 212 | Crea `ScrapingLog` |
| `_start_portal_heartbeat(...)` / `beat()` | 220/235 | Hilo de heartbeat: escribe logs periódicos para no ser marcado huérfano |
| **`_run_scraping(job_id)`** | 264 | **Lógica principal** (ver abajo) |
| `scraping_task(self, job_id)` | 718 | `shared_task` de Celery |
| `scraping_task_run(job_id)` | 725 | Entrada para hilo local |

### 6.1 `_run_scraping(job_id)` — lógica principal
1. Carga el `ScrapingJob`; si no existe, termina.
2. **Claim CAS**: `UPDATE ... SET estado='running', execution_token=<uuid> WHERE id=job AND estado='idle'`; si no afecta 1 fila, el job ya fue reclamado → sale.
3. Toma `portales` de `parametros` (o `ORDEN_DEFECTO`); activa `_keep_windows_awake` en Windows.
4. **Por cada portal:**
   - Omite portales ya `completed` en `resultados_por_portal` (reanudación parcial).
   - Respeta `stopped` / `paused` (espera activa con `time.sleep(2)`).
   - Crea/reanuda la ejecución con `lifecycle.start_or_resume_portal_run(job, portal)`.
   - Instancia la skill del portal y la ejecuta con `checkpoint_page` y `resume_item_ids`.
   - `reportar_progreso(payload)` (inner): refresca el job, respeta pausa/cancelación, actualiza `progreso`, `procesadas`, `total_propiedades`, `nuevas/actualizadas/errores`, y guarda `checkpoints`/`resume_item_ids` por portal.
   - Al terminar: `finalize_portal_run(portal_run)` (aplica ciclo de vida) o `fail_portal_run(...)` si hubo error no reintentable.
5. Al acabar todos los portales marca `completed` y guarda `resultados_por_portal` + contadores finales.

> **Reanudación segura:** si un job muere a mitad, al hacer `resume` desde `error/stopped` se vuelve `idle` y al relanzarse **reutiliza el `token` de la ejecución del portal** (almacenado en `job.parametros['lifecycle_runs']`) y el checkpoint por portal, continuando donde quedó.

---

## 7. Ciclo de vida de publicaciones — `ingestas/lifecycle.py`

| Función | Rol |
|---|---|
| `_min_coverage()` | Umbral mínimo de cobertura (default `SCRAPING_LIFECYCLE_MIN_COVERAGE=0.65`) |
| `_misses_to_retire()` | Ausencias para retirar (default `2`, mínimo 2) |
| `start_or_resume_portal_run(job, portal)` | Atómico: crea `EjecucionPortal` o reutiliza su `token` al reanudar el mismo job |
| `fail_portal_run(run, reason, status)` | Cierra la ejecución como `error/incomplete` sin tocar publicaciones |
| `finalize_portal_run(run)` | Cierra y aplica ausencias **solo si la cobertura es confiable** |

Reglas de `finalize_portal_run`:
- La primera ejecución completa de un portal es **línea base** (`es_linea_base`).
- Si la ejecución no vio propiedades → `incomplete`.
- Si la cobertura frente a la ejecución anterior confiable es < 65% → `incomplete` (no toca publicaciones).
- Si es confiable: las propiedades vistas se marcan `activa`; las no vistas suman ausencia; **1 ausencia = posible retirada, 2 consecutivas = retirada confirmada**.

---

## 8. Watchdog — `scraping_watchdog.py` (comando)

`python manage.py scraping_watchdog`
- Bucle que recupera jobs **huérfanos** (ejecutores muertos entre instancias de Azure).
- `_recover_orphan(stale_seconds, max_resumes)`: reabre/reanuda jobs con host muerto.
- `_can_execute_here(job)`: solo el host indicado en `parametros['execution_host']` (o cualquiera si no aplica) puede tomar el job → **aislamiento por host**.
- `_is_recoverable_error(job)`: decide si un error es recuperable.

---

## 9. Skills por portal — `intelligence/skills/scrapi/`

Cada portal es una subclase de `BaseSkill` con `validate_params(params)` y `execute(params, context) -> SkillResult`. Están registradas en el `SkillRegistry` de intelligence al arrancar.

| Skill | Archivo | Funciones de apoyo |
|---|---|---|
| `ScraperOrchestratorSkill` | `scraper_orchestrator.py` | `_instanciar_skill(portal)` (72) — orquesta el portal correcto |
| `ScraperRemaxSkill` | `scraper_remax.py` | `_limpiar_locks_stale` (35), `_ejecutar_scraping` (58), `report` (73), `estandarizar_lote` (93) |
| `ScraperAdondevivirSkill` | `scraper_adondevivir.py` | `_limpiar_locks_stale` (29), `_ejecutar_scraping` (46) |
| `ScraperProperatiSkill` | `scraper_properati.py` | `_ejecutar_scraping` (27) |
| `ScraperUrbaniaSkill` | `scraper_urbania.py` | `_estandarizar_urbania` (30), `_ejecutar_scraping` (146) |
| `ScraperFacebookMarketplaceSkill` | `scraper_facebook_marketplace.py` | `execute` (38) — caso especial |

**Mecánica común de cada scraper-skill:**
1. Abre/recupera su perfil Camoufox dedicado (carpeta `camoufox_session_<portal>`), limpiando locks viejos.
2. Navega el listado del portal con paginación.
3. Extrae propiedades y las estandariza (función `estandarizar_lote` / `_estandarizar_urbania`): mapea títulos, precios (USD/PEN), áreas, distritos, URLs, imágenes.
4. Llama a `db_utils.guardar_propiedades(lista, fuente, lifecycle_run_id=run.id)`.
5. Notifica progreso vía el callback de la skill (que el motor traduce a `ScrapingJob`).

**Caso Facebook Marketplace:** requiere sesión iniciada (login con captcha/2FA) por lo que el alcance de ejecución es `local_interactive` en Windows con escritorio visible; en Azure el motor lo `deferre`/maneja con cuidado (job aislado por host).

### `db_utils.py`
- **`guardar_propiedades(propiedades, fuente, lifecycle_run_id=None) -> {nuevas, actualizadas, errores, total}`**
  `update_or_create(fuente, id_origen, defaults=...)`. Si hay `lifecycle_run`, además fija los campos de vida: `estado_publicacion='activa'`, `ultima_vez_vista=now`, borra ausencia/retiro, vincula `ultima_ejecucion_vista`, y setea `primera_vez_vista` en la primera vez.
- **`limpiar_fuente(fuente) -> int`**: borra todas las propiedades de un portal (para re-scrapear desde cero).

---

## 10. Última implementación (resumen de cambios recientes)

La iteración más reciente del módulo añadió robustez para producción (Azure):

1. **Aislamiento de jobs por host y portal** (`dafa2801`): cada job puede reanudarse portal por portal; `execution_host` decide qué instancia puede ejecutarlo; se evita repetir portales ya completados.
2. **Claim con `execution_token` (CAS)**: evita que dos ejecutores procesen el mismo job (estados `idle → running`).
3. **Checkpoints y `resume_item_ids` por portal**: guardados en `job.parametros` para reanudar en la página/ítem exacto.
4. **Ciclo de vida de publicaciones** (`lifecycle.py` + campos en `PropiedadesCompetencia` + `EjecucionPortal`): altas, ausencias y retiros confirmados solo con ejecuciones confiables (línea base + cobertura ≥ 65 % + 2 ausencias).
5. **Heartbeat por portal** para no ser considerado huérfano en ejecuciones largas.
6. **Watchdog** para recuperar huérfanos entre instancias.
7. **Recuperación de ejecución de scraping** (`100b509a`, ya integrada): reconciliación de jobs stale y cierre seguro de Camoufox.
8. **Reporte preciso de fallos de autenticación de Facebook** (`2b52530b`): distingue error de sesión/login de errores reintentables.

---

## 11. Capítulo aparte — Campos nuevos para la línea de tiempo de m² por mes y por área

### 11.1 Problema actual
`PropiedadesCompetencia` guarda **solo el último estado** de cada propiedad (se actualiza *in place* con cada ejecución). Esto permite ver "qué hay hoy", pero **no permite construir una serie temporal** del precio y del precio/m² por mes para analizar tendencias por área.

Para una **línea de tiempo "precio y m² por mes y por área"** (ej.: evolución del precio/m² de departamentos en Cayma por mes, o por rangos de área) se necesita histórico.

### 11.2 Enfoque recomendado: tabla histórica append-only

Crear una tabla de **snapshots mensuales/por ejecución** (una fila por propiedad por mes) sin tocar la tabla vigente:

**Modelo propuesto — `HistoricoPrecioArea` (tabla `historico_precio_area`)**

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | PK | |
| `propiedad` | FK → `PropiedadesCompetencia` (o `fuente`+`id_origen` si se quiere denormalizado) | Propiedad observada |
| `fuente` / `id_origen` | Char | Denormalizado para consultas sin JOIN |
| `mes` | Date (primer día de mes) | Periodo del snapshot |
| `area_construida_m2` | Decimal | Área construida en ese momento |
| `area_terreno_m2` | Decimal | Área de terreno (para terrenos) |
| `area_utilizada_m2` | Decimal | Área que se usa para el cálculo de m² (construida salvo terrenos) |
| `precio_usd` | Decimal | Precio en USD del snapshot |
| `precio_soles` | Decimal | Precio en PEN del snapshot |
| `moneda_original` | Char | USD / PEN |
| `precio_m2_usd` | Decimal | Calculado: `precio_usd / area_utilizada` (por tipo de inmueble) |
| `precio_m2_soles` | Decimal | Ídem en soles |
| `tipo_inmueble` | Char | Para agrupar por tipo |
| `distrito` / `zona` | Char | Para análisis por área/zona |
| `estado_publicacion` | Char | `activa / retirada` en ese mes |
| `ejecucion_vista` | FK → `EjecucionPortal` | Qué ejecución lo observó |
| `creado_en` | DateTime | |

**Índices útiles:** `(fuente, mes)`, `(distrito, tipo_inmueble, mes)`, `(tipo_inmueble, mes)`.

### 11.3 Escritura del histórico
- Al finalizar cada `EjecucionPortal` confiable (`finalize_portal_run`), tomar las `PropiedadesCompetencia` vistas en esa ejecución y **upsert** por `(propiedad, mes)` en `HistoricoPrecioArea` (un snapshot por propiedad por mes — si hay varias ejecuciones el mismo mes, se conserva la última o la mediana según configuración).
- El cálculo del m² se hace con la misma lógica que `acm.utils.calcular_precio_m2` (usa área construida salvo terrenos que usan área total) para **mantener consistencia** con el resto del sistema.

### 11.4 Lectura / análisis (línea de tiempo)
- **Serie mensual por zona/distrito y tipo:** `SELECT mes, distrito, tipo_inmueble, AVG(precio_m2_usd) ... GROUP BY mes, distrito, tipo_inmueble ORDER BY mes`.
- **Por rango de área:** bucket por `area_utilizada` (p. ej. <50, 50–100, 100–150, 150+).
- Dashboard de tendencia: línea por mes del `precio_m2` (mediana) y de oferta (`COUNT(*)`) por distrito/zona y tipo; permitir filtrar por rango de área.

### 11.5 Campos adicionales (opcionales, sobre `PropiedadesCompetencia`)
Si no se quiere una tabla separada (histórico corto), se pueden añadir campos *delta* a la tabla vigente:

| Campo | Descripción |
|---|---|
| `precio_m2` (Decimal) | Precio/m² calculado del último snapshot (para ordenar/filtrar sin calcular) |
| `primer_precio_usd_visto` | Primer precio registrado (inicio de la línea) |
| `precio_usd_anterior` | Precio del snapshot anterior |
| `ultimo_cambio_precio_en` | Fecha del último cambio de precio |
| `veces_precio_cambiado` | Contador de cambios |

> Recomendación: usar la **tabla histórica** (11.2) para el análisis temporal y mantener `PropiedadesCompetencia` solo como estado vigente; los campos de 11.5 sirven como acceso rápido.

---

*Fin del documento.*
