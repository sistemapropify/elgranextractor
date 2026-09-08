# Estabilización integral de Propifai

## Estado y objetivo

Este documento es el contrato operativo entre CRM, n8n, respondedor inicial, motor IA, shadow, scraping, dashboards y despliegue. Ningún dashboard debe inferir éxito a partir de la ausencia de una excepción.

## Fuentes de verdad

| Dominio | Fuente autoritativa | Productor | Consumidores |
|---|---|---|---|
| Propiedades propias | Azure SQL `propifai`: `property`, `property_specs` y catálogos | CRM Propifai | respondedor, agentes, shadow, dashboards |
| Conversaciones | `dbo.lead.chat_history` | CRM/n8n/WhatsApp | análisis CRM, reconciliador shadow |
| Respuesta inicial | `n8n_property_bot_initial_response` | endpoint del respondedor | dashboard nocturno, auditoría |
| Draft shadow | `prometeo_bot_response_draft` | reconciliador/motor shadow | dashboard Calidad del motor IA |
| Evaluación contextual | modelos `lead_intelligence` por `source_lead_id + history_hash + version` | analizador incremental | dashboards CRM |
| Scraping | `ScrapingJob`, `ScrapingLog`, `PropiedadRaw` | worker de scraping | dashboard de ingestas |
| Trabajos durables | `prometeo_durable_job` en la BD `default` existente | endpoints/manual/cron | worker SQL con lease |
| Despliegue | health profundo + activos estáticos | workflow GitHub/Azure | gate de publicación |

No se autoriza crear otra base de datos. Los datos funcionales continúan en `propiextractor/propifai` según los aliases existentes.

## Estados canónicos

Todo proceso debe exponer uno de estos estados, sin mezclar significados:

- `pending`: aceptado, aún no iniciado.
- `running`: proceso vivo con heartbeat reciente.
- `completed`: terminó y cumplió el contrato.
- `empty`: terminó correctamente sin resultados.
- `degraded`: produjo salida mediante fallback o con advertencias.
- `needs_review`: hay evidencia concreta que requiere revisión humana.
- `failed`: no pudo completar el contrato.
- `stale`: figura activo, pero perdió heartbeat.
- `unavailable`: dependencia externa no disponible; no equivale a error de datos.

`sin datos`, `pendiente`, `revisión` y `error` nunca deben representarse con el mismo estado.

## Invariantes transversales

1. Un código `PROP` exacto y único identifica la propiedad. El título es evidencia secundaria.
2. Respondedor y shadow comparten el mismo motor determinista para mensajes con código.
3. Un tipo nuevo de propiedad usa un contrato genérico verificado; no se declara inexistente.
4. `bot` se normaliza como respuesta del agente automático en `chat_history`.
5. Cada mensaje CRM se identifica de forma idempotente por lead, emisor, timestamp, posición y contenido.
6. Una evaluación solo está vigente para el `history_hash` y versión que la produjo.
7. Un trabajo largo requiere propietario, lease/bloqueo, heartbeat, checkpoint, cancelación cooperativa y resultado final.
8. Un despliegue solo es exitoso si health, base de datos requerida y archivos estáticos responden correctamente durante una ventana estable.

## Hallazgos verificados

### Respondedor de propiedades

Antes existían dos falsos negativos: `TITLE_CODE_MISMATCH` bloqueaba un código exacto y una lista cerrada rechazaba tipos nuevos. Además, una prueba esperaba un motor compartido inexistente. Se creó `initial_property_decision.py`; ahora respondedor y shadow usan la misma decisión.

### CRM y análisis

El parser ya reconoce `lead`, `agent` y `bot`, normalizando `bot` como `agent`. Las evaluaciones contextuales se versionan por hash, pero el refresco depende de barridos programados.

### Shadow

La captura en vivo nace desde el endpoint inicial y se completa con un reconciliador durable. En `shadow_live` se leen todos los mensajes del lead cuyo registro cambió en el periodo (`lead.updated_at`), no solo los leads ingresados ese día. Cada mensaje usa una clave SHA-256 estable de lead, emisor, timestamp, posición y contenido; los eventos ya persistidos se omiten.

### Tareas programadas

Los disparadores manuales y programados ya no crean hilos daemon ni dependen de Celery `memory://` para análisis, reconciliación shadow o scraping. Persisten primero un `DurableJob` en Azure SQL y después despiertan un proceso worker. Un lease vencido permite reclamar el trabajo tras un reinicio; la clave `dedupe_key` evita dobles ejecuciones lógicas.

### Scraping

`ScrapingJob` conserva el estado funcional, logs, heartbeat y checkpoints; `DurableJob` es ahora el propietario de la ejecución, reintentos y lease. “Detener” cancela ambos registros y libera el lease. Camoufox continúa requiriendo sus librerías nativas en la imagen/startup de Azure; la cola durable evita pérdida y duplicación, pero no sustituye esas dependencias.

### Despliegue

El workflow valida health y estáticos, pero la estabilidad del proceso y las tareas largas siguen dependiendo del App Service. El gate debe separar fallo de autenticación Azure, fallo de startup, fallo de base y fallo de estáticos.

## Orden obligatorio de estabilización

1. Resolver y probar propiedad exacta compartida (implementado localmente).
2. Implementar reconciliador CRM → shadow idempotente (implementado localmente).
3. Sustituir threads daemon y broker `memory://` por ejecución durable para análisis, shadow y scraping (implementado localmente).
4. Unificar estados y métricas de dashboards.
5. Separar definitivamente el worker de scraping en un servicio/contenedor dedicado; lease/checkpoint/heartbeat ya están implementados localmente.
6. Endurecer el gate de despliegue y pruebas E2E.
7. Publicar solo después de la matriz de regresión.

## Matriz mínima de regresión

- Código exacto con título comercial diferente responde y registra advertencia.
- Tipo conocido usa plantilla específica.
- Tipo desconocido usa plantilla genérica sin LLM.
- Propiedad vendida/no visible no responde.
- Mensaje duplicado no genera segunda respuesta.
- `bot` cuenta como respuesta en CRM.
- Mensaje CRM nuevo genera un solo draft shadow.
- Actualización del hilo invalida únicamente su evaluación anterior.
- Trabajo de scraping detenido no conserva estado `running`.
- Reinicio recupera desde checkpoint.
- Deploy falla de forma diferenciada ante 503, DB o estáticos.
## Implementación durable actual

- Modelo: `lead_intelligence.DurableJob`, tabla `prometeo_durable_job` dentro de la base `default` ya existente.
- Tipos: `lead_analysis`, `shadow_reconcile` y `scraping`.
- Estados: `pending`, `running`, `completed`, `failed`, `cancelled`.
- Recuperación: un worker puede reclamar `running` con lease vencido y continúa usando los checkpoints del trabajo funcional.
- Reintentos: máximo configurable por trabajo; el intento y el error quedan persistidos.
- Cancelación: análisis y scraping cancelan también su `DurableJob`; el worker no sobrescribe `cancelled` al terminar.
- Despertador: `run_durable_worker --once` drena toda la cola disponible. El endpoint programado vuelve a despertarlo, por lo que un reinicio no pierde el trabajo persistido.
- Restricción respetada: la migración `0008_durablejob` crea solo una tabla en la base existente; no crea otra base de datos ni otro recurso Azure.

## Criterios de aceptación verificados

- Dos encolados con la misma clave producen un solo trabajo.
- Un trabajo `running` con lease vencido se recupera y aumenta su número de intento.
- Una activación `--once` procesa todos los pendientes, no únicamente el primero.
- Si el análisis principal ya está activo, shadow se sigue reconciliando.
- Shadow selecciona conversaciones por `updated_at` y deduplica cada mensaje.
- “Detener” no permite que análisis o scraping vuelvan a aparecer como activos.
