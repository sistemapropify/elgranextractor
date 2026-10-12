# Archivo de datasets ML en Azure Blob

El servicio archiva únicamente filas de `ingestas_mldatasetentry` de cortes
antiguos. Conserva los metadatos del corte en `ingestas_mldatasetsnapshot` y
una referencia verificable dentro de `coverage._blob_archive`, sin migración
de esquema. No modifica propiedades, observaciones fuente, conversaciones,
respuestas de IA, datos de leads ni historial de ACM.

## Política

- Conservar los cinco cortes más recientes en SQL (mínimo configurable: dos).
- Conservar todos los cortes con entrenamientos asociados, de cualquier estado.
- Archivar los restantes sin esperar días adicionales, para controlar el
  crecimiento de SQL. La edad mínima es configurable si se necesita.
- Contenedor privado `ml-dataset-archives` en la cuenta Azure ya configurada.
- Archivos JSONL comprimidos con gzip, uno por corte, con metadatos del corte,
  todos los campos de sus entradas, evidencia de observación y regla espacial.
- Nombre por ID y SHA-256; no sobrescribir copias existentes.
- Descargar, comprobar SHA-256, descomprimir y verificar el número de filas
  antes de retirar entradas SQL. La retirada y su manifiesto son atómicos.
- No hay borrado automático de archivos Blob ni política de caducidad en ellos.

## Revisión y activación

La preparación local mantiene el archivado automático desactivado. La página
`/acm/modelos/` muestra a administradores la política, versiones pendientes,
versiones archivadas y cantidad de registros trasladados. Se puede consultar el
plan sin subir archivos ni modificar filas:

```powershell
python manage.py archive_ml_datasets
```

Después de autorizar el despliegue, ejecutar el primer lote en el entorno que
accede a SQL y Blob:

```powershell
python manage.py archive_ml_datasets --apply --limit 10
```

Para continuar el mantenimiento, configurar en ese entorno:

```text
ML_DATASET_ARCHIVE_ENABLED=True
ML_DATASET_ARCHIVE_CONTAINER=ml-dataset-archives
ML_DATASET_KEEP_RECENT=5
ML_DATASET_ARCHIVE_MIN_AGE_DAYS=0
```

El worker `ml_candidates_worker` revisa la política antes de generar cortes,
en lotes de hasta diez por hora. No realiza mantenimiento mientras la opción
esté desactivada. Un fallo de Blob deja intacto el corte fallido y no detiene
por sí mismo el resto del pipeline. Cortes ya archivados no se procesan otra vez.

Las descargas CSV históricas siguen leyendo el corte desde SQL o Blob. Una
copia inaccesible o dañada produce error 503, nunca un CSV vacío presentado
como éxito. Los lectores de entrenamiento y comparación también aceptan Blob.

## Recuperación

Para devolver un corte a SQL, con capacidad disponible, detener/desactivar el
mantenimiento automático durante la recuperación:

```powershell
python manage.py archive_ml_datasets --restore 123 --apply
```

La restauración verifica la copia completa y recupera las entradas con sus IDs
originales en una transacción. Conserva la copia Blob. Si SQL no tiene espacio,
la restauración revierte y la copia sigue disponible. No aplicar `SHRINK` ni
reconstruir índices automáticamente: se busca liberar páginas para nuevas
escrituras, no cambiar el tamaño contratado del servicio.

El primer uso crea el contenedor privado si aún no existe, con las credenciales
actuales de Azure Storage. Si un contenedor existente tiene acceso público, el
servicio lo rechaza. No requiere trasladar las fotos ni cambiar sus enlaces.

## Validación local

```powershell
python manage.py test ingestas.tests.test_ml_dataset_archive --settings=ingestas.tests.quality_settings --noinput
```

Las pruebas usan SQLite aislado y Blob en memoria. Cubren retención,
integridad, fallos de subida/descarga, reversión SQL, reintentos, restauración,
igualdad de CSV, lectura de entrenamiento, permisos y mantenimiento.
