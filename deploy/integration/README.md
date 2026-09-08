# Integración del proyecto — 8 de septiembre de 2026

Base: `origin/main` (`f4ead8d4`) y los tres commits publicados del scraper, hasta `c6c016c5`. Rama de trabajo: `codex/integracion-proyecto-20260908`.

## Contenido y decisiones

- Scraping: conserva la versión validada de paginación, scroll infinito, deduplicación, normalización, URL configurable, recuperación y telemetría. Su worker usa `ScrapingJob` y la imagen fijada de `deploy/scraping`; no se traslada a la cola general.
- Motor semántico: incorpora el paquete pendiente de `56a0f307`, sus evaluaciones y contratos. Es una biblioteca disponible para integración; este cambio no sustituye automáticamente el enrutamiento del ChatProcessor por el planificador semántico.
- Conversaciones web: lista, creación y lectura por identidad de sesión; título derivado del primer mensaje y compatibilidad con conversaciones antiguas. La escritura conserva CSRF.
- Leads y respuestas: incorpora la cola SQL pendiente de `.codex-fix-urbania`, con deduplicación, leases, heartbeat, reintentos limitados y protección frente a resultados de un intento antiguo. Los errores de análisis se propagan al worker. El scraper mantiene su propio mecanismo de recuperación.
- Citas: separa eventos Visita y Captación, mantiene el contrato exclusivo de visitas para las propiedades y muestra citas de captación y citas comerciales en resultados y cohortes. El CRM se consulta con SELECT; la evidencia se almacena en la base de Prometeo.
- n8n: reúne la decisión compartida y la plantilla de hoteles con la lógica vigente de disponibilidad, coincidencia de propiedad, captación programada e idempotencia. Mantiene el mecanismo actual de plantillas configurables de remarketing.
- Conserva las mejoras posteriores de main para control de leads, API móvil, campañas, inicio de sesión y alertas. Los commits de respaldo y sus copias antiguas no se mezclan completos.

Se revisaron los cambios de los worktrees principal, 0fd3, b1d1, `.codex-deploy-camoufox` y `.codex-fix-urbania`, así como los documentos pendientes de 4590. Se integró contenido seleccionado y se resolvieron los solapamientos; los worktrees originales no se modificaron. Los documentos en `plans/` describen el estado histórico de sus respectivas tareas, no certifican el estado actual de producción.

## Migraciones

La migración local `0008_durablejob` pasa a `0011_durablejob`, después de `0010_lead_control`, evitando dos ramas del grafo. Se añaden migraciones de conciliación del estado de modelos que ya divergían de sus migraciones: identificadores automáticos de AnalysisRunStep/MotorAIControl, nombres de índices de n8n y metadatos de PropertyProspect. No se eliminan tablas ni datos. La tabla explícita y la predeterminada de PropertyProspect tienen el mismo nombre físico.

## Validación aislada

El workflow `Project integration validation` se ejecuta al publicar esta rama o abrir una solicitud de integración. No tiene credenciales de producción ni tareas de despliegue.

1. Construye la imagen fijada del scraper y la imagen de pruebas complementaria, con dependencias y hashes.
2. Ejecuta Camoufox y el dashboard real sin red ni descargas.
3. Ejecuta las regresiones del scraper y `python -m integration_suite` con SQLite y bloqueo de HTTP externo.
4. Comprueba la consistencia entre modelos y migraciones.
5. Crea un SQL Server temporal y ejecuta persistencia, recuperación, control de leads, móvil, conversaciones y las consultas reales de visitas/captaciones.

Las pruebas de identidad crean tablas de fixtures con los modelos reales, sin ejecutar las migraciones históricas de `intelligence`; las migraciones de los módulos integrados sí se ejecutan. Esto no sustituye un ensayo del grafo histórico completo sobre una copia de la base de producción.

## Operación

`startup.sh` inicia el worker durable separado de Gunicorn. `DURABLE_EXECUTION_MODE=external` evita procesos por solicitud; `DURABLE_WORKER_ENABLED=0` permite usar un servicio externo. Antes de activar el código en un entorno deben haberse aplicado sus migraciones. Los trabajos se conservan en `prometeo_durable_job`; el log del proceso es `/home/LogFiles/durable-worker.log`, con id, tipo, intento y resultado. La cancelación del análisis es cooperativa y se comunica en el siguiente heartbeat; no interrumpe instantáneamente una llamada ya iniciada.

Los trabajos son de entrega al menos una vez. La recuperación evita que un intento antiguo marque como terminado un intento nuevo; los consumidores deben conservar su idempotencia. Un bloqueo registrado por el motor sombra se consulta en el borrador correspondiente.

Publicar esta rama no actualiza `main` ni producción. Un push a `main` sí dispara el despliegue de toda la aplicación. La activación del worker dedicado del scraper y una prueba controlada en producción siguen siendo pasos de despliegue; las restricciones de los portales, incluido el 403 observado en detalles de Remax, no desaparecen por integrar código.
