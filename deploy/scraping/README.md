# Worker de scraping

Estado: implementación integrada en `codex/scraping-integral-20260908`, sobre la
revisión compartida `f4ead8d4`. Linux, navegador sin red y SQL Server aislado
pasaron en [CI](https://github.com/sistemapropify/elgranextractor/actions/runs/34240278527).
No se ha desplegado ni migrado producción.

## Qué cambia

La web configura búsquedas, crea trabajos en SQL y consulta eventos mediante
peticiones cortas. Un worker independiente consume esa cola. Camoufox y sus
bibliotecas se instalan al construir su imagen, antes de aceptar trabajos.

Cada trabajo conserva la URL, su ámbito y la versión del adaptador. Los cuatro
portales paginados comparten descubrimiento, deduplicación, guardado y recuperación;
sus extractores de tarjetas y fichas siguen siendo específicos de cada portal.
Marketplace mantiene su recorrido por scroll y conserva los IDs de cada lote.

Los límites, bloqueos, repeticiones y estancamientos quedan identificados como
recorridos incompletos. Las fichas fallidas quedan pendientes; no impiden descubrir
las páginas siguientes. Los checkpoints se confirman después del guardado. Un
token y un permiso de escritura con vencimiento impiden escribir desde un proceso
reemplazado. La evidencia de la última página se guarda junto con su checkpoint.

Las observaciones se separan por búsqueda. Una ejecución parcial o un cambio de
URL no retira anuncios de otra búsqueda. Marketplace no se utiliza para confirmar
retiros por ausencia del feed. El histórico sin ámbito exige una nueva línea base.

## Construcción y pruebas

Desde la raíz del repositorio, en Docker Linux con arquitectura amd64:

```sh
docker build --platform linux/amd64 --build-arg SCRAPING_REVISION="$(git rev-parse HEAD)" -f deploy/scraping/Dockerfile -t scraping-worker:review .
docker run --rm --network none --entrypoint python scraping-worker:review -m scrapi.worker_smoke
docker run --rm --network none --entrypoint python scraping-worker:review -m scrapi.dashboard_smoke
```

El navegador se verifica por SHA256, y se registra como versión activa para que
Camoufox también resuelva las fuentes desde esa instalación. La imagen fija su
base por digest, las dependencias Python por versión/hash, Debian por snapshot y
ODBC por versión. Actualizar esas referencias requiere reconstruir y pasar las
pruebas; las versiones del proyecto se conservaron, sin una actualización global
de Django que afecte otros módulos.

El workflow `scraping-worker.yml` construye la imagen, abre/cierra el navegador sin
red, ejecuta las regresiones y prueba migraciones/persistencia contra un SQL Server
aislado. No publica imágenes ni despliega recursos. La primera ejecución completa
pasó; la rama ejecuta nuevamente estos controles con cada actualización del scraper.
La batería local final contiene 105 pruebas; también se verificó el dashboard real
en Camoufox con respuestas HTTP aisladas: vista previa, CSRF, URLs, filtros, logs
como texto, cobertura y reanudación.

La imagen debe pasar los controles aunque la aplicación web siga funcionando.
`entrypoint.sh` verifica el navegador y exige migraciones ya aplicadas; no ejecuta
una migración automática ni instala paquetes al arrancar.

## Configuración del worker

Suministrar secretos mediante el mecanismo existente de Azure, nunca en la imagen:

- `DJANGO_SECRET_KEY`.
- `SCRAPING_DB_HOST`, `SCRAPING_DB_NAME`, `SCRAPING_DB_USER`, `SCRAPING_DB_PASSWORD`.
- Configuración existente de Blob: `AZURE_STORAGE_CONNECTION_STRING`, o cuenta/clave;
  `AZURE_STORAGE_CONTAINER_NAME` cuando corresponda.
- Para Marketplace: sesión autorizada en `FACEBOOK_MARKETPLACE_COOKIES_JSON` o
  volumen del perfil dedicado en `FACEBOOK_MARKETPLACE_PROFILE_DIR`.

No montar el perfil de una sesión local que esté abierta en otro worker.
El contenedor corre como UID 10001; los volúmenes del perfil deben permitirle escritura.
Conservar los tiempos de espera acotados: `CAMOUFOX_LAUNCH_TIMEOUT`,
`CAMOUFOX_TOTAL_TIMEOUT`, `SCRAPING_MAX_PAGES` y los límites de Marketplace.
Alcanzar un límite conserva resultados y pendientes; no certifica inventario completo.

La web debe usar `SCRAPING_EXECUTION_MODE=external` al activar este worker. Ese modo
encola sin abrir navegadores ni iniciar otro watchdog dentro de Gunicorn. La
interfaz consulta la señal del worker y muestra cuándo no hay actividad reciente.
El estado de trabajos y los errores persistidos son las primeras señales operativas;
`python manage.py scraping_metrics` exporta métricas JSON de cola, candidatos,
portales y señales de fallo para conectarlas al monitor existente.
`python manage.py scraping_health` comprueba el heartbeat del propio host y sale
con error si falta; se utiliza como HEALTHCHECK del contenedor. Otro host activo
no oculta la caída del worker local. `--any-worker` comprueba la disponibilidad global.
Estos comandos no envían mensajes a personas; el destino de avisos externos pertenece
a la configuración del monitor.

Detener con margen de cierre, por ejemplo `docker stop --time 120 <worker>`.
SIGTERM conserva candidatos/checkpoint y devuelve el trabajo activo a la cola.
Un trabajo pausado conserva la pausa y puede reanudarse con un nuevo ejecutor.
Ante una terminación forzosa, el vencimiento del permiso de escritura permite
recuperar el trabajo sin aceptar escrituras del proceso anterior.

## Despliegue coordinado con otros módulos

1. La rama de integración parte de `f4ead8d4`; conserva los cambios compartidos de
   los demás módulos y las migraciones móviles de startup. Comprobar si main avanzó
   antes de publicar. No desplegar el checkout original `e629ef2d` completo.
2. Revisar migraciones `0016_propiedad_lifecycle` a `0019_scraping_history_repair` junto
   con cualquier migración paralela. Resolver ramas de migración sin renumerarlas a ciegas.
3. Exigir el workflow Linux/SQL exitoso en el commit que se publicará. Completar la validación
   de Azure con `azure-validate`. Conservar imagen y configuración actuales para revertir.
4. Pausar/terminar trabajos activos; aplicar las migraciones aditivas en una ventana
   coordinada. Hacer respaldo y revisar el SQL generado contra la versión real del servidor.
5. Publicar la web integrada y activar un único worker dedicado con los secretos
   existentes. El cambio inicial de web puede reiniciarla; separar el worker permite
   desplegar sus actualizaciones posteriores sin reiniciar los otros módulos.
6. Usar Vista previa desde el dashboard, después una corrida piloto completa. Comparar
   IDs descubiertos, guardados, pendientes, duplicados y motivo de parada.
7. Revisar la corrida piloto y su evidencia antes de ampliar la operación.

Reversión: detener el worker nuevo y restaurar el artefacto/configuración anteriores.
Conservar las tablas aditivas y los candidatos para diagnóstico; no revertir las
migraciones eliminando evidencia durante una incidencia. No ejecutar dos versiones
distintas del worker sobre los mismos trabajos durante la transición.

## Diagnóstico e histórico

Desde `webapp`, estas pruebas de listados no guardan propiedades ni suben imágenes:

```sh
python -m scrapi.diagnostic urbania --start-page 5 --max-pages 8 --output urbania.json
python -m scrapi.diagnostic remax --start-page 32 --max-pages 36 --output remax.json
python -m scrapi.diagnostic facebook_marketplace --max-items 120 --output marketplace.json
```

La vista previa del dashboard usa el mismo motor en la cola del worker y muestra
una muestra en `preview.result`. El resultado de una muestra nunca representa el
inventario entero. Cambiar una URL cambia la búsqueda; un cambio de estructura HTML
puede seguir requiriendo actualizar y validar el adaptador.

El histórico tiene auditoría, aplicación y reversión implementadas:

```sh
python manage.py scraping_audit_history --portal urbania --output propuestas.jsonl
python manage.py scraping_repair_history --input propuestas.jsonl
python manage.py scraping_repair_history --input propuestas.jsonl --apply
python manage.py scraping_repair_history --rollback UUID_DEL_LOTE
python manage.py scraping_repair_history --rollback UUID_DEL_LOTE --apply
```

La auditoría admite los cinco portales y solo propone cambios respaldados por el
ID y datos crudos. Genera hasta 1000 propuestas por lote; `--after-id` permite
continuar. Las operaciones simulan por defecto. Al aplicar, se vuelve a calcular
la propuesta y se comprueba que los valores y evidencia no cambiaron. El diario
SQL guarda antes/después y hash en la misma transacción que la corrección.
Un conflicto cancela el lote completo. La reversión no sobrescribe actualizaciones
posteriores del scraper. No se ejecutaron reparaciones sobre producción.

Anuncios sin evidencia suficiente y retiros anteriores sin ámbito no se corrigen
por conjetura. Una extracción nueva verifica lo que continúa publicado; solo
recorridos completos comparables pueden evaluar ausencias posteriores.

`python manage.py scraping_prune_logs --days 30` simula retención de eventos de
trabajos terminados. `--apply` elimina los eventos elegibles por lotes. No se ha
programado ni ejecutado esta eliminación. Archivar/exportar evidencia necesaria
antes de activarla. Los logs no incluyen cookies, cabeceras de autorización ni
HTML completo de respuestas; el dashboard permite filtros y exportación NDJSON.

## Límites de la verificación

Hay evidencia real de los listados y del scroll, pruebas con escenarios controlados,
persistencia SQLite/SQL Server y arranque real de Camoufox Linux sin red. La activación
requiere revisar el entorno real y verificar una extracción completa con guardado
y almacenamiento de imágenes en producción. Ninguna de estas pruebas garantiza
que un portal externo deje de cambiar o de restringir el acceso.
