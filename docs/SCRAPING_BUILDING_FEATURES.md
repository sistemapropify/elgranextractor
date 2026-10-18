# Cocheras y ascensor en el scraper

Implementación local del 17 de octubre de 2026. No publicada en producción.

## Contrato

Casas, departamentos y oficinas de RE/MAX, Properati, Adondevivir, Urbania y
Facebook Marketplace usan `scrapi.building_features`. Los cuatro portales
paginados recogen características del detalle después de validar la URL de la
misma propiedad; Facebook utiliza sus campos y descripción disponibles.
No se analiza el cuerpo completo de una página ni anuncios recomendados.

La cantidad conserva la columna existente `estacionamientos`. Los nuevos
atributos se persisten en claves independientes de `datos_crudos`:

- `tiene_cochera`: true, false o null.
- `tipos_cochera`: lista de `lineal_techada`, `lineal_no_techada`,
  `paralela_techada`, `paralela_no_techada`, o null.
- `tiene_ascensor`: true, false o null.
- `_building_features`: versión, fecha observada, estados, fragmentos de
  evidencia con campo de origen, grupos parciales y condiciones.

No se crean nuevas columnas físicas ni se modifica el esquema SQL remoto.
Las propiedades del modelo exponen esos datos a la tabla, galería y Excel.
Los históricos sin metadatos se interpretan al leerlos, sin escritura implícita.

Un cero expresamente publicado significa «Sin cochera». El silencio del anuncio
significa «Sin información». Una cochera opcional o de visitas no se suma como
incluida. Si faltan disposición o cubierta no se inventa un tipo; si hay grupos
distintos se conservan ambos. Las contradicciones quedan señaladas.
Un ascensor futuro no se confirma como existente; su existencia no certifica
que funcione. Una lectura incompleta conserva datos previos confirmados con
marca de reconfirmación. Los campos protegidos de revisión se respetan.

## Reprocesar evidencia ya archivada

Ejecutar desde `D:/PROMETEO` con el entorno y base de datos que se desee revisar:

```powershell
& 'D:/PROMETEO/elgranextractor/venv/Scripts/python.exe' webapp/manage.py reprocesar_cocheras_ascensor --portal remax --batch-size 100 --limit 100
```

Por defecto simula: no modifica registros ni avanza un archivo de cursor.
`--apply` guarda; `--cursor-file RUTA` conserva el último lote confirmado y
reanuda usando el mismo portal/base; `--after-id ID` permite reanudar manualmente.
`--database ALIAS` selecciona la conexión configurada. Sin `--limit` recorre
todos los registros aplicables. El comando no abre navegadores ni recupera
información que nunca se archivó. No se ejecutó `--apply` contra producción
durante esta entrega.

## Verificación realizada

- 108 pruebas en SQLite aislado: normalización de los cinco portales,
  guardado/recarga, ceros, campos desconocidos, tipos mixtos, contradicciones,
  protección manual, idempotencia, Excel, HTML y reprocesamiento reanudable;
  regresiones de precio, áreas, antigüedad, piso y recuperación del scraper.
- 60 anuncios archivados de tres portales leídos sin escritura: RE/MAX,
  Properati y Adondevivir. 27 tenían tipo clasificable y 23 ascensor explícito.
- Dashboard local autenticado: 39 columnas alineadas y ejemplos reales de
  «Sin cochera», «Paralela techada», «Sí» y «Sin información».
- RE/MAX público presentó verificación de seguridad. La inspección en vivo
  de los cinco portales queda pendiente; las pruebas con entradas controladas
  no equivalen a una extracción completa en sus sitios actuales.

```powershell
& 'D:/PROMETEO/elgranextractor/venv/Scripts/python.exe' webapp/manage.py test ingestas.tests.test_building_features ingestas.tests.test_apartment_floor ingestas.tests.test_scraping_export ingestas.tests.test_scraping_integrity ingestas.tests.test_scraping_recovery ingestas.tests.test_facebook_marketplace_scraper scrapi.test_remax_data scrapi.test_properati_age scrapi.test_detail_age --settings=ingestas.scraping_test_settings --noinput --verbosity=0
```

El respaldo previo de los archivos modificados y las comprobaciones locales
están en `outputs/scraper-building-features-20261017/`. Ninguna de estas pruebas
necesita iniciar una extracción de producción.
