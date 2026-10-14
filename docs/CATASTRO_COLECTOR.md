# Catastro: recolector y dashboard local

Código del módulo: `webapp/catastro/`. Motor: `webapp/scrapi/geollaqta_scraper.py`.
Skill: `webapp/intelligence/skills/scrapi/scraper_geollaqta.py`, registrada en
`intelligence/apps.py`, contrato BaseSkill, nivel 4, sin caché de ejecuciones.
No se añade al recorrido automático de portales comerciales: usa otra entidad,
catastro, y no guarda datos en PropiedadExterna ni cambia RE/MAX o Properati.

Dashboard: `/catastro/`, entrada Catastro del menú lateral. Sólo administradores.
El mapa sigue en Cuadrantización. Publicación del módulo autorizada el 14/10/2026;
usa el pipeline de producción existente. En Azure, `CATASTRO_DATA_DIR` apunta a
`/home/data/catastro`; las credenciales privadas de R2 se suministran mediante
configuración de la aplicación. Los originales se recuperan de R2 si no están
en la copia local. Se importaron los 12 índices del piloto sin copiar los PDF
y las fotografías al almacenamiento de Azure.

## Inicio y reanudación

Desde el dashboard elegir distrito y «Descargar distrito completo». Se recorren
todos los registros encontrados, con todas sus fichas, reportes y fotos
disponibles. No hay un selector de cantidad ni un límite de predios por
ejecución. El proceso sigue aunque se cierre la página. «Detener» se aplica
antes de la siguiente solicitud. Una nueva ejecución salta los predios ya
archivados; «Reintentar documentos pendientes» consulta los documentos fallidos.
El estado distingue descarga de un lote terminada de cobertura completa del distrito.
Cada ejecución muestra el inventario real, los registros ya archivados y los
que faltan. Los grupos internos de 100 geometrías se procesan en secuencia
dentro de la misma ejecución, sin acumular el distrito completo en memoria
ni pedir otro inicio por grupo. Reanudar salta lo ya guardado; reintentar
pendientes revisa cada predio pendiente una sola vez durante esa ejecución.

También desde PowerShell, sin Django ni acceso a la BD de propiedades:

```powershell
& D:/PROMETEO/elgranextractor/venv/Scripts/python.exe D:/PROMETEO/scripts/collect_geollaqta.py --ubigeo 040117 --lot 04011713059004 --limit 1
& D:/PROMETEO/elgranextractor/venv/Scripts/python.exe D:/PROMETEO/scripts/collect_geollaqta.py --ubigeo 040126
```

Por defecto cada ejecución abarca todo el distrito y hay una sola ejecución
activa. CLI y skill conservan un límite opcional de 1–500 sólo para pruebas;
el dashboard nunca lo envía. CLI, dashboard y skill usan el mismo
motor, trabajo y estado. Fallos o procesos muertos pueden reanudarse; el
heartbeat vence en cinco minutos. COFOPRI se consulta en serie, al menos un
segundo entre solicitudes; errores de acceso o almacenamiento detienen el lote.

## Archivos y datos

R2 privado: `geollaqta/UBIGEO/ID_LOTE/`. Cada documento mantiene su nombre original
de la tabla de Geollaqta, número de ficha y record_id real. Se descargan todos los
tipos `ficha*.php` que aparecen en la galería, todos los reportes y todas las fotos
enlazadas; no se corta en la primera ficha ni en las diez filas visibles.

PDF original: `ficha-RECORD_ID-HASH.pdf` o `reporte-RECORD_ID-HASH.pdf`.
Imagen: nombre original más hash. Cambios de contenido conservan archivos previos.
`datos.json` es el índice actual; `datos-HASH.json` conserva la instantánea de cada
consulta. Los hashes, bytes y URL de origen permiten auditar cada archivo.

Por cada documento se guardan texto de todas las páginas, tablas, celdas,
posiciones y campos numerados (número, sección, etiqueta, valores y filas).
Campos vacíos usan null. Los datos complementarios sin número y los textos
sin asociación se conservan por separado. La asociación semántica se marca
`requires_validation`: preservar todos los textos/celdas no equivale a garantizar
la interpretación automática de cualquier formato. PDFs escaneados o diseños
desconocidos requieren OCR/revisión posterior, nunca valores inventados.

Se verificó el diseño individual y bienes comunes del lote 04011713059004,
incluyendo vía, servicios, registros vacíos y cuatro filas de construcción.
Otros formatos se conservan completos y requieren validación del extractor.

## Configuración y límites

Secretos fuera de Git en `%USERPROFILE%/.codex/secrets/prometeo-catastro-r2.env`.
Alternativas: `CATASTRO_R2_CREDENTIALS_FILE` o variables `R2_ACCOUNT_ID`,
`R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`. No se aceptan claves,
endpoints ni rutas arbitrarias en parámetros web o de la skill.

Índice SQLite y copia local: `outputs/geollaqta-archive/`, configurable con
`CATASTRO_DATA_DIR`. Es un índice local del piloto; D1 no está implementado.
Originales y JSON van a R2. Se retiró el límite acumulado de 1 GB del piloto;
no hay un máximo fijo de predios. Los archivos de más de 20 MB se identifican
como pendientes. En Azure sólo quedan el índice SQLite y las copias de trabajo
que todavía no se han confirmado en R2. Después de verificar una carga, se
retiran sus nuevas copias de trabajo; se conservan las copias de revisión
preexistentes. Los índices JSON y originales se consultan directamente de R2
si no existe copia local. En desarrollo se conservan las copias locales.

La compatibilidad PUT/HEAD/GET y región auto siguen la
[documentación S3 de R2](https://developers.cloudflare.com/r2/api/s3/api/).
Cada carga se confirma con longitud y metadato SHA256 vía HEAD. No se expone R2
públicamente. Documentos sólo se sirven tras autenticación y permiso administrativo.

Pruebas: `python -m unittest catastro.test_collector` desde `webapp/`.

## Lectura y presentación de reportes

`catastro/report_fields.py` lee los reportes con sus encabezados de columna;
es un diseño distinto de la ficha numerada. Conserva los valores azules y
negros, ambos titulares, campos vacíos y medidas de cada lindero. Los textos
sin asociación se guardan para auditoría y no se presentan como campos.

«Documento completo · formato original» muestra páginas renderizadas del PDF
archivado, con sus líneas, tablas y fotografía originales. La ruta de páginas
exige el mismo permiso administrativo que el archivo y responde PNG privado.

`catastro.reextract.reextract()` vuelve a extraer los PDF locales, verifica sus
hashes y actualiza el índice actual y una nueva instantánea JSON en R2. No
descarga de nuevo la fuente ni modifica los PDF o fotografías originales.
