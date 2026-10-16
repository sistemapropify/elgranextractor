# Visor de planos y Catastro maestro

## Objetivo aceptado

Completar los distritos sin cobertura de Geollaqta con otras fuentes, por
ejemplo archivos DWG del catastro de Cayma. Antes de incorporar una fuente,
el administrador necesita saber qué geometrías, capas, atributos y referencias
geográficas contiene. Los sistemas de coordenadas de los archivos son variados
o desconocidos: no debe asumirse UTM WGS84 por ser un plano de Arequipa.

Nombre propuesto: **Catastro maestro**. Es la vista consolidada del sistema.
**Fuentes catastrales** es el catálogo de archivos y servicios que lo alimentan.
**Visor de planos** es el espacio para inspeccionar y preparar cada incorporación.

## Tamaño del archivo: corrección confirmada

El usuario corrigió el tamaño a **14,7 MB**; la cifra anterior en GB queda
descartada. El lector ya recibe DWG nativo y esta instancia admite hasta 100 MB
por original. La anterior entrada GeoJSON fue reemplazada por la carga DWG.

Para el archivo actual no se requiere diseñar una transferencia multigigabyte.
Antes de afirmar compatibilidad CAD, comprobar su versión, entidades y referencia
geográfica. El mapa debe consumir derivados por capa y ámbito espacial para no
necesitar el DWG original durante cada movimiento o cambio de zoom.

## Recorrido

1. Cargar el archivo como una fuente en revisión, conservando el original.
2. Inspeccionar capas, tipos de entidad, atributos, unidades y extensión.
3. Identificar el CRS/datum y comprobar la ubicación. Si falta, mantener la
   fuente sin aporte al maestro y preparar georreferenciación con puntos de
   control. Asignar un CRS y desplazar un dibujo son operaciones diferentes.
4. Ver qué capas sirven: lotes, manzanas, vías, construcciones, rótulos, usos u
   otras. Conservar sus nombres originales y pedir confirmación del destino;
   el nombre de una capa no prueba su significado catastral.
5. Comparar con las fuentes existentes; mostrar coincidencias y discrepancias.
6. Guardar la fuente y confirmar las capas que aportarán al maestro.
7. Activar o desactivar una fuente completa o capas individuales. Desactivar
   retira su aporte de las consultas actuales, sin borrar sus archivos ni historial.

## Trazabilidad y consolidación

- Fuente: identificador estable, nombre, distrito, organismo o autor cuando se
  conozca, fecha real del levantamiento si está documentada, fecha de ingreso,
  hash, versión, estado, CRS, unidades y validación de posición.
- Capa: identificador, fuente/versión, nombre original, destino confirmado,
  tipos geométricos, número de entidades, estilo y si aporta al maestro.
- Elemento: identificador original CAD cuando exista, fuente, capa, geometría
  original y transformada, atributos originales y vínculos confirmados con
  elementos de otras fuentes. No usar identificadores CAD como partidas registrales.
- Dato normalizado: valor, documento/campo de origen, estado de validación y
  reglas explícitas de selección. Conservar valores en conflicto.
- Auditoría: quién importó, georreferenció, incorporó o desactivó y cuándo.

La fecha de carga no sustituye la fecha del catastro. No sumar duplicados ni
elegir automáticamente una geometría por ser el archivo más reciente. Geollaqta
conserva sus registros y documentos originales. Un polígono DWG puede completar
geometría o atributos disponibles, pero no crea una ficha, titular, partida o
área registral que el archivo no contenga. Las áreas geométricas del dibujo se
etiquetan por separado de las declaradas en fichas y reportes.

La consolidación debe consultar sólo fuentes y capas activas. Cada cambio
incrementa una revisión del maestro e invalida su caché. Las consultas futuras
usan la nueva revisión; informes históricos conservan la revisión que utilizaron.
Los permisos de Catastro, Cuadrantización y ACM siguen siendo independientes.

## Arquitectura propuesta (pendiente de implementar)

- Originales inmutables e índices derivados privados en R2. Catálogo y estados
  separados de los binarios; no almacenar PDF o DWG en la base de propiedades.
- Trabajo de conversión aislado, asíncrono y reanudable en Azure. El visor muestra
  estado, advertencias y entidades no admitidas. Convertir una vez por versión,
  no cada vez que se mueve o amplía el mapa.
- API común del maestro por distrito, extensión, capa y revisión. GeoJSON para
  ámbitos pequeños; evaluar teselas vectoriales para distritos completos.
- Cuadrantización consume esa misma API mediante su tarjeta de catastro; no
  necesita saber si el origen era COFOPRI, DWG u otro formato. El visor permite
  comparar la fuente en revisión con el maestro antes de incorporarla.
- El catálogo permite desactivar aportes y revertir versiones sin eliminar originales.

## Referencias evaluadas y bibliotecas

- QGIS: importación DWG/DXF, selección de subcapas, bloques, curvas y CRS.
  https://docs.qgis.org/3.44/en/docs/user_manual/managing_data_source/opening_data.html
- ArcGIS Pro: validación de posición CAD, asignación de CRS y puntos de control.
  https://pro.arcgis.com/en/pro-app/latest/help/data/cad/georeferencing-cad-data.html
- Autodesk Viewer / APS: aislamiento de elementos y capas, propiedades y medición.
  https://aps.autodesk.com/viewer-sdk
- ODA File Converter: conversión DWG a DXF; validar licencia y despliegue servidor
  antes de adoptar para el servicio comercial. No está instalado ni contratado.
  https://www.opendesign.com/guestfiles/oda_file_converter
- ezdxf: lectura DXF, capas, bloques, textos y polilíneas. No lee DWG por sí solo;
  su adaptador ODA requiere el conversor externo.
  https://ezdxf.readthedocs.io/en/stable/addons/odafc.html
- pyproj: transformación entre CRS/datum conocidos, antes de exportar a WGS84.
  https://pyproj4.github.io/pyproj/stable/
- Shapely: validación geométrica, operaciones espaciales y detección de conflictos.
  https://shapely.readthedocs.io/en/stable/manual.html
- Google Maps JavaScript Data: presentación GeoJSON, selección y estilos por capa.
  https://developers.google.com/maps/documentation/javascript/datalayer

No se requiere una segunda librería de mapas para el visor inicial. APS es
una alternativa si se necesita fidelidad CAD/3D avanzada, sujeta a evaluación
de integración, procesamiento y condiciones comerciales.

## Estado local actualizado: lector DWG

Ruta: `/catastro/visor-planos/`, acceso administrativo igual al módulo Catastro.
Plantilla `webapp/templates/catastro/visor_planos.html`, archivos JS/CSS propios,
botones y tarjetas oscuras sin añadir Bootstrap. Mapa principal y cinco tarjetas
colapsables: archivo, capas, vista/medición, elemento seleccionado y exportación.

La entrada se corrigió a DWG nativo: carga privada, conservación del original,
lectura en segundo plano mediante GNU LibreDWG y ezdxf, catálogo de capas y
geometrías paginadas. Vista CAD sin coordenadas confirmadas; Google Maps tras
seleccionar el CRS correcto. Detalles y límites en `docs/LECTOR_DWG.md`.

Pendiente: aprobación de fuentes en R2, georreferenciación por puntos de control,
confirmación y desactivación de aportes, consolidación del maestro e integración
con Cuadrantización. El DWG real ya se leyó en local y Azure: 35 capas,
102.978 entidades y 102.962 dibujables. Sigue pendiente confirmar su CRS/datum
y aprobar qué capas aportarán al maestro.

## Integración con ACM — 16/10/2026

Permiso `cadastral_info`, categoría «Mapa y capas», configurable por rol y
aplicado en cada API. Se incluye por defecto en el ACM básico; una política
explícita permite desactivarlo para un rol. Administrador tiene acceso completo.
La vista de perspectiva aplica la política del rol seleccionado.

La nueva optimización local consulta los lotes que intersectan un círculo del
radio seleccionado, con geometría WGS84 calculada en metros. El inventario
incluye distritos vecinos y usa lotes completos, sin cortar sus contornos.
El distrito/numeración de la tarjeta se obtiene del lote seleccionado.

La cobertura permanece anclada al punto de la primera carga: mover el pin dentro
de ese círculo, incluso por calles entre lotes, conserva el conjunto. Si el pin
entra en un lote ya cargado que sobrepasa el círculo, también se reutiliza.
Al salir de la cobertura se consulta un nuevo radio; cambiar el radio también
actualiza la selección. Pan y zoom no consultan ni eliminan los lotes.

El inventario espacial trae identificadores y sólo se descargan geometrías
pendientes, en tandas de hasta 500 y con dos peticiones simultáneas. Los lotes
comunes con coberturas anteriores se reutilizan. Se conservan tres coberturas,
incluidas las vacías. El reintento completa pendientes, sin rehacer el inventario.
Mover el pin durante una descarga no la cancela mientras siga en su cobertura;
las respuestas de una cobertura abandonada no pueden sustituir la actual.

Tarjeta flotante «Información catastral», de 260 px y con cierre independiente:
fachada, códigos, año publicado del catastro y datos documentales verificados.
Áreas y perímetros provienen de la ficha; el reporte completa los campos ausentes
de la misma unidad. No se usan áreas de capas, geometría ni otra unidad como
reemplazo. Los datos faltantes permanecen explícitos. No se entregan propietarios,
DNI ni el documento completo a través de esta tarjeta. El selector separa unidades.

Proveedor reutilizable `catastro/master.py` y `catastro-master-data.js`; Google
Maps sólo presenta los vectores. Geollaqta es el primer proveedor activo. El DWG
no aporta todavía datos al maestro. Fuentes/versionado y aprobación siguen pendientes.

Cuadrantización incluye números de lote/manzana obtenidos de los vectores ya
cargados. Canvas único, sin marcadores adicionales ni peticiones extra: manzanas
desde zoom 17, lotes desde zoom 18, control de superposición y casilla para ocultar.
Cuando la capa de manzanas está desactivada, sus códigos se agrupan desde los lotes
visibles; al activarla se usa la geometría de manzana para posicionar el rótulo.

Verificación: 126 pruebas ACM y 36 Catastro (una de fixture nativo omitida),
pruebas Node del transporte, geometría, galería, medidas, numeración y widget;
activos locales HTTP 200 con comparación de bytes. APIs sin sesión: 401.
Caso real 04012607038027: manzana 07/038, 48 lotes, sin inventario distrital.
La integración ACM, numeración, Street View y recuperación del visor se incluyen
en la publicación integral posterior a 8053415f. El resultado del despliegue se
comprueba en GitHub Actions. El visor también recupera bloqueos transitorios
del archivo de estado en Windows. El CRS de los DWG sigue pendiente de confirmar.


### Corrección de distrito completo y acceso básico — publicación solicitada

Posterior a f32f1c09; incluida en esta publicación. Su estado se comprueba en
GitHub Actions, sin asumir éxito por el envío. 71 pruebas Python de permisos/ACM
pasaron, junto con la prueba Node de 1.201 lotes, movimiento durante descarga,
calles, dibujo progresivo, cambio de distrito, caché y recuperación de pendientes.
Se recibieron y validaron los 5.240 lotes actuales de Yanahuara en 11 tandas;
el proveedor identifica el lote 04012607038027 en ese conjunto completo.
Los JS v2 responden por HTTP local con bytes verificados; sin sesión la API
sigue devolviendo 401. La sesión del ACM local requiere el login real de Propify.


### Tarjeta flotante, numeración y disponibilidad de documentos

La tarjeta pertenece al contenedor del mapa, sin reducir su altura. Muestra
fachada, códigos, año y medidas; no incluye el contador del distrito, controles
de capas, relaciones con zonas, galería ni enlaces a fichas. Se puede mover y
cerrar sin ocultar los polígonos. La siguiente ubicación del pin la reabre.
La fachada pública del mismo lote carga directamente en el navegador; un fallo
de consulta documental no debe impedir ver una imagen disponible.

ACM reutiliza la numeración Canvas de lotes/manzanas con minZoom=0 y
lotMinZoom=0. No añade peticiones ni marcadores; evita rótulos superpuestos.
Cuadrantización conserva sus umbrales 17/18. Los vectores del ACM no se ocultan
con el zoom ni se recargan al desplazar el mapa.

La API distingue documento verificado, documento no publicado y consulta
no disponible. Un fallo de red no equivale a un campo vacío del documento.
Las áreas/perímetros siguen saliendo de la ficha o del reporte, sin calcularlos
a partir de las capas. El navegador distingue carga pendiente y error recuperable.

Comprobación real: el lote 04010483021014 tiene reporte con terreno 201.49 m²,
construcción 248.98 m² y perímetros 10.00 / 19.78 / 19.67 / 10.00 m. Su reporte
y fachada se archivaron en R2 y se comprobó la lectura desde Azure. La ficha
individual permanece pendiente; no se la reemplaza por una ficha inventada.
La conexión directa desde Azure al origen agota el tiempo de espera; un ensayo
con un Worker autenticado tampoco pudo descargarlo y queda fuera de la aplicación.
Por tanto los documentos no archivados todavía dependen de resolver ese acceso.
No se ha iniciado una extracción masiva ni configurado un relay en Azure.


### Optimización por radio — publicación solicitada

Posterior a 5c050e3e; publicación solicitada. El resultado se comprueba en
GitHub Actions. Contrato de configuración revisión 3, scope radius.
La carga completa del distrito queda sustituida en ACM por el radio seleccionado.
La prueba real de 500 m alrededor de 04010483021014 recibió 1.532 lotes,
669.984 bytes y cinco peticiones en 2,01 s. El proveedor los convirtió sin
pérdidas, identificó el lote y no hizo peticiones adicionales al mover el pin
11 m dentro de la cobertura. Son resultados de esa consulta, no una estimación
de cobertura ni una garantía de latencia para todos los radios.

Pruebas automáticas: reutilización dentro del círculo, calles, lote de borde,
vecinos de otro distrito, radio distinto, regiones previas/vacías, conservación
de lotes comunes, lotes >1.000, recuperación de pendientes y cancelación/retorno.
La tarjeta flotante, fachada, permisos y datos documentales se conservan.
La limitación de acceso en vivo a documentos desde Azure sigue siendo independiente.


## Shared ACM and Cuadrantización document reader — 2026-10-16
Both maps now use `catastro.map_report.report_measurements` and a shared,
verified 15-minute report cache, keyed by lot and individual unit. The ACM keeps
individual-form priority and fills missing fields from that same unit's report.
Neither reader uses GIS areas as a fallback. Old archive extraction revisions
are read again before their fields can be used. Failed reads are not cached.

The source reader uses the same headers and 25-second request timeout in both
maps, with one interactive attempt per download. The ACM request deadline allows
for the gallery, individual form and report; aborting or changing the pin still
cancels the browser request and ignores stale responses. District geometry is
still limited to the selected radius and reuses the previously loaded footprint.

The floating card tries the primary facade image and suffixes `_1` through `_11`,
with bounded image attempts and stale-lot protection. Report failures do not stop
facade discovery. Missing images remain missing rather than displaying a PDF.

Validation: 106 isolated Django tests and four JavaScript regression suites
passed. A live local read of lot 04010222013014 returned land 369.71 m²,
construction 469.52 m² and boundaries 11.73 / 38.44 / 38.81 / 12.27 m in about
four seconds; the other map reused the same result without a second source read.
Its source gallery has no images and the twelve usual facade URLs return 404.


### One HTTP response path for both map cards — 2026-10-16
The ACM lot endpoint now delegates directly to `cuadrantizacion.geollaqta.report_response`,
the same response handler used by the Cuadrantización report endpoint. It no longer
runs the separate master-summary discovery path before reading a report. Each entry
point retains its existing authentication and active-role checks. The document reader
prefers a readable individual form for the selected unit and fills blanks from that
unit's report; a form-only unit can also be read. Shared cache revision 3 contains only
verified measurements, report selectors and facade locations.

Tests assert identical JSON and failure responses for both HTTP cards, ACM access
without a Prometeo login, denied-role rejection before document access, separate units,
form priority, report fallback and a successful retry after source failure.

Production diagnosis separately confirmed that the application container timed out
connecting to COFOPRI after 25 seconds. A trial of the existing Cloudflare connector
also failed and its original placement was restored; it remains disconnected from
ACM. No new server, proxy, paid plan or infrastructure was enabled.

The reported lot 04010217042011 was recovered with the existing single-lot collector:
two original reports and one facade uploaded with hash verification to private R2.
The two individual-form endpoints returned HTTP 500 and remain explicitly pending.
The deployed reader in Azure returned its verified archive in 0.951 seconds with
the source deliberately disconnected for that read test. This repairs that archive;
it does not establish general live connectivity for unarchived properties.
