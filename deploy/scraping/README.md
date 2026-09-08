# Worker de scraping

Estado: implementación local. No se ha desplegado ni migrado producción.

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
```

El navegador se verifica por SHA256, y se registra como versión activa para que
Camoufox también resuelva las fuentes desde esa instalación. La imagen fija su
base por digest, las dependencias Python por versión/hash, Debian por snapshot y
ODBC por versión. Actualizar esas referencias requiere reconstruir y pasar las
pruebas; las versiones del proyecto se conservaron, sin una actualización global
de Django que afecte otros módulos.

El workflow `scraping-worker.yml` construye la imagen, abre/cierra el navegador sin
red, ejecuta las regresiones y prueba migraciones/persistencia contra un SQL Server
aislado. No publica imágenes ni despliega recursos. Los paquetes/hash se han
resuelto localmente; el build Linux y las pruebas SQL del workflow siguen pendientes
de ejecución porque este equipo no dispone de Docker.

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
los avisos externos a personas aún requieren definir destino y umbrales.

## Despliegue coordinado con otros módulos

1. Integrar estos cambios sobre la revisión compartida más reciente. Este worktree
   parte de `e629ef2d`; no publicar su aplicación completa encima de cambios más nuevos.
2. Revisar migraciones `0017_scraping_integrity` y `0018_scraping_worker_lease` junto
   con cualquier migración paralela. Resolver ramas de migración sin renumerarlas a ciegas.
3. Pasar el workflow Linux/SQL y revisar el artefacto exacto. Completar la validación
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

`python manage.py scraping_audit_history --output propuestas.jsonl` genera propuestas
de corrección de precios/áreas de Urbania desde datos crudos, con valores anteriores
y hash de evidencia. Es solo lectura. La aplicación de correcciones, revisión de
estados históricos y anuncios sin evidencia suficiente sigue siendo una tarea de
datos que debe revisarse con respaldo; no se ejecutó contra producción aquí.

`python manage.py scraping_prune_logs --days 30` simula retención de eventos de
trabajos terminados. `--apply` elimina los eventos elegibles por lotes. No se ha
programado ni ejecutado esta eliminación. Archivar/exportar evidencia necesaria
antes de activarla. Los logs no incluyen cookies, cabeceras de autorización ni
HTML completo de respuestas; el dashboard permite filtros y exportación NDJSON.

## Límites de la verificación

Hay evidencia real de los listados y del scroll, pruebas de políticas con escenarios
controlados y pruebas de persistencia SQLite. Falta ejecutar Linux/SQL en CI, revisar
la migración en el entorno real y verificar una extracción completa con guardado
y almacenamiento de imágenes en producción. Ninguna de estas pruebas garantiza
que un portal externo deje de cambiar o de restringir el acceso.
