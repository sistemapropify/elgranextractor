# Catastro Maestro: implementación verificable, 21/10/2026

## Entornos

El checkout compartido es D:/PROMETEO. La aplicación Django está preparada en http://127.0.0.1:8000/catastro/maestro/fuentes/, con sesión administrativa. No se ha publicado Django en producción.

El usuario autorizó crear D1, el Worker privado y el acceso OAuth de Wrangler. Se desplegaron D1 prometeo-catastro-maestro (2769a97f-54f7-48d7-b7a8-83da2f7389a6) y https://prometeo-catastro-maestro.sistema-propify.workers.dev en la cuenta 21f5983cc6703b36f8657d1867b74250. Worker versión 391e6746-b624-4d1f-83cd-1f6e8d30627a; DB sólo a la D1 nueva, sin CORS ni observabilidad. El Worker COFOPRI anterior no fue modificado. Credenciales privadas fuera del repositorio y del navegador.

D1 es la autoridad durable; la caché de edición está en RAM por distrito. Originales y derivados se conservan en R2 con SHA256. El estado anterior exclusivamente RAM y el impedimento de acceso al perfil Cloudflare quedaron superados por la autorización posterior.

La migración histórica JSON → tablas y la nueva extracción COFOPRI siguen detenidas. Registrar un plano o implementar un componente no levanta ninguna de esas restricciones.

## Funciones disponibles

- Contrato catastro-maestro-v1, UUID internos y códigos oficiales separados como texto; territorio, UBIGEO, postal y divisiones de cada fuente distintos.
- Tablas de fuentes/versiones, entidades, aportes por campo, selección, personas/documentos y relaciones, medios, antecedentes registrales, segmentos múltiples, zonas y atributos actuales tipados e indexados.
- Versiones inmutables, comparación previa, completar vacíos, sustitución por campos/ámbito, retiro y recuperación. Sin fusiones por nombre o proximidad. Retirar geometría conserva identidades, titulares y documentos.
- Confirmación atómica D1 por revisión e idempotencia; descarta caché no confirmada ante fallos. Historial nuevo por diferencias, compatible con las revisiones iniciales.
- Consulta por territorio, urbanización, sector/manzana/lote, partida, DNI, usos/actividad y rangos. Ficha privada con varios titulares, PDF/fotos, lados y antecedentes; uso catastral, observado, actividad/CIIU y zonificación separados.
- Gestor de PDF en RAM, originales recuperables desde R2, versiones y distrito de trabajo. Respaldo Cayma 2006 oculto inicialmente y fuera de aportes automáticos ACM.
- Contrato cartográfico común para visor/ACM/Cuadrantización; geometría activable sólo con posición declarada verificada y evidencia. El mapa compartido excluye atributos documentales privados.
- Normalizador futuro COFOPRI, original inmutable verificado en R2 e indexación candidata sólo de futuras revisiones 3. No se ejecutó sobre nuevas extracciones reales ni históricos.
- Calibración afín propuesta con al menos cuatro puntos de ajuste y dos independientes de comprobación, EPSG proyectado en metros, evidencia por punto, tolerancia explícita, errores y envolvente. Guardar conserva una versión pendiente sin activar geometría. Estas cantidades son reglas del prototipo, no una norma catastral oficial; un error pequeño no acredita precisión absoluta.

## Conversión vectorial del sector 32

Nueve capas originales del dibujo principal: manzanas, lotes, códigos de manzana, rótulos tradicionales de manzana, números de lote, cotas de lados, nombres de calles, cuadras y aranceles. SVG conserva curvas originales; DXF contiene 25 capas e incluye lecturas y propuestas, aproximando las curvas con segmentos. Hay CSV de lotes, lados, manzanas y anotaciones, JSON completo y visor autónomo con búsqueda/selección y localizador de 26.01.

Resultados pendientes de cotejo: 438 caras cerradas candidatas, 255 con número de lote propuesto, 15 códigos de manzana leídos, 11 contornos de esa capa cerrados por trazos originales, 462 lados con cota asociada, 127 caras convexas cuadriláteras con propuesta completa de orientación y 23 propuestas de esquina con dos calles distintas. No equivalen a lotes homologados. Los demás casos quedan pendientes, no falsos ni cero; frente a parque permanece desconocido.

Se corrigió la agrupación de números de dos cifras. Se cotejaron visualmente el rótulo de lote 10 del candidato S32-F0213 y su cota 26.01 en L03; también una esquina propuesta junto a CA Melgar y PJ El Retiro. La inspección de muestra no sustituye el cotejo completo. Rótulos como JARDIN no se convierten en números de lote ni en parques por suposición.

Código de manzana y rótulo tradicional se conservan separados. 280 caras tienen asociación por contención a un código y 155 a un rótulo tradicional. Los cuatro contornos de manzana que no cerraron no se completaron inventando líneas. Las cotas son longitudes anotadas, no áreas; no se deducen unidades ni área en m² de las coordenadas del dibujo. Los segmentos pueden ser múltiples; no se impone frente principal en esquinas.

La geometría está en puntos de la página PDF girada, origen superior izquierdo y Y hacia abajo. DXF invierte Y y tiene INSUNITS=0. El PDF contiene medidas relativas /Subtype /RL, sin coordenadas geográficas incrustadas verificables. El usuario no dispone de DWG/DXF ni puntos de control adicionales. Posición geográfica pendiente; no se usó el plano impreciso 2006 como control.

Los 26 archivos del paquete están en R2 y la versión D1 es vectores:fec0bfb7101863fc584264f09ede7c3749ec4c52, revisión de composición 4. Conserva el PDF original, enlaza los derivados privados y no incorpora filas de inmuebles ni aportes activables. El gestor ofrece Ver capas vectoriales y Abrir PDF; los archivos requieren sesión administrativa y verificación SHA256 al recuperarse.

Copia de consulta: G:/Mi unidad/DriveSyncFiles/200 - PROYECTOS/PROPIFY/CATASTRO/SECTOR 32/REVISION VECTORIAL/. El ZIP contiene 25 archivos; el HTML funciona también desde esa carpeta.

## Validación y límites

91 pruebas Python aprobadas: maestro, D1, indexación, calibración, asociaciones vectoriales, archivos privados, capas y colectores retenidos. Tras normalizar CRLF para el hash CSP del visor se repitieron sus dos pruebas específicas. Pasaron comprobaciones Node del Worker privado, geometría y respaldo Cayma. DXF auditado sin errores ni reparaciones; SVG analizados como XML. Assets principales cotejados por hash contra HTTP local; rutas administrativas reales rechazan acceso anónimo. El visor recuperado desde R2 funcionó con CSP restrictiva.

D1 conserva un proyecto Cayma de 34 láminas y dos fuentes. Hay una de 34 láminas, cero inmuebles/geometrías nuevos activados. No se calculó cobertura territorial. Registrar versiones no aumenta la cantidad de láminas.

Caché de edición: 64 MB/250k filas por distrito; consulta tabular: hasta 1000 resultados; cambios: hasta 12 MB y presupuesto de consultas de la base actual; fila menor de 1.8 MB. Los excesos fallan explícitamente. No está probada la escala de todo Arequipa.

## Pendiente

Cotejo de rótulos/cotas, cierre topológico y homologación; controles fiables y revisión de georreferenciación/uniones; otras 33 láminas según disponibilidad; piloto COFOPRI completo autorizado, recuperación sin duplicados, documentos/roles y medición de tiempos. La incidencia general de roles ACM no queda resuelta por este módulo.

Mercado/publicaciones, deduplicación, actores/proyectos/interiores, zonas de valor e indicadores siguen el plan rector. La migración histórica y la nueva extracción continúan bloqueadas; publicar Django requiere la instrucción correspondiente.

## Dashboard de planos y extracción inicial (21/10/2026)

Se añadió `/catastro/maestro/planos/`, con inventario PDF/DWG, resumen por UBIGEO, etapas derivadas, láminas previstas por proyecto, geometrías activas, accesos a calibración/homologación y carga de DWG. Los PDF registrados en D1/R2 se pueden vectorizar desde el panel; los registros PDF nuevos intentan la extracción automáticamente. El extractor `prometeo-pdf-vector-v1` conserva caminos y palabras como GeoJSON en R2, enlazado a una nueva versión candidata en D1. Las coordenadas se marcan `LOCAL_PDF_PAGE_POINTS`, nunca como geográficas.

La extracción genérica no clasifica caminos como lotes, manzanas, lados o cotas, no infiere un EPSG y no ejecuta OCR. Esas etapas requieren revisión/homologación. El DWG existente se convierte e inventaría en el visor, pero sus archivos y estados todavía están en el almacenamiento local de la instancia y no forman parte del inventario durable D1/R2. No se activan geometrías ni se modifica el respaldo Cayma, JSON histórico o extracción COFOPRI.

Límites actuales del PDF: hasta 12 MB, 100 páginas, 120 000 trazos y 250 000 palabras; el GeoJSON derivado debe ser menor de 19 MB. Si excede límites o R2 no está disponible, el PDF original ya registrado permanece y el dashboard ofrece reintentar; los PDF escaneados quedan sin OCR. El proceso es síncrono y requiere medir tiempos antes de usar lotes grandes. Estos cambios están sólo en el checkout local; no se publicó Django ni se amplió el esquema D1.

## Catálogo incremental universal (22/10/2026)

Se amplió el contrato compatible con D1 para registrar información sin esperar
una validación global de toda la ciudad. Las migraciones aditivas
`004_universal_catalog.sql` y `005_administrative_addresses.sql` ya fueron
aplicadas a la D1 real y el Worker privado reconoce las nuevas tablas.

Nuevas estructuras durables:

- Jerarquía administrativa versionada y varias direcciones precisas por entidad.
- Definiciones extensibles de atributos y observaciones tipadas con vigencia,
  método, estado y evidencia.
- Identificadores externos separados de los identificadores internos y de los
  códigos oficiales.
- Publicaciones e historial de cambios de anuncios.
- Operaciones documentadas, separadas de los precios de oferta.
- Organizaciones, actividades económicas y correspondencias CIIU versionadas.
- Visitas, proyectos, etapas y relaciones proyecto-inmueble.
- Capas ambientales/vectoriales no parcelarias.
- Registros de cobertura por distrito y conjunto de datos.

Cada fila conserva `source_version`. Las filas nuevas entran como candidatas y
no se publican por el solo hecho de existir en D1. La ficha puede consultar
identificadores, direcciones, observaciones, anuncios, historial de precios,
transacciones, actividades, organizaciones, visitas y proyectos.

El contrato de ejemplo está en `docs/CATASTRO_CATALOGO_INGESTA.md`. El Worker
incorpora un contrato estático de columnas para evitar que una carga con todas
las secciones consuma el límite de consultas de D1. Las pruebas de Python del
maestro y del transporte D1, y la prueba del Worker, pasan.

La aplicación Django con el nuevo contrato está preparada para el checkout
local; falta publicarla sin interrumpir la extracción COFOPRI que esté activa.

## Revisión, importación progresiva y capas de entorno (22/10/2026)

Se añadió el tramo operativo que faltaba entre registrar candidatos y activar
aportes:

- Revisión por registro con estados `candidate`, `observed`, `verified`,
  `rejected`, `superseded` y `expired`.
- Estado vigente y eventos append-only con autor, motivo, evidencia y revisión.
- Historial consultable por registro desde la interfaz administrativa.
- Exclusión predeterminada de capas rechazadas y consulta GeoJSON privada por
  UBIGEO, tipo, estado y extensión.
- Importación desde el contrato completo, GeoJSON de entorno o NDJSON de una
  sección, con un máximo de 30.000 filas y 12 MB por tanda.
- Historial de anuncios entre versiones mediante `listing_id` o
  `portal` + `external_id`.

La migración D1 `006_catalog_review.sql` fue aplicada: la base quedó con 36
tablas y 0.81 MB, sin filas sintéticas ni cambios a los registros existentes.
El Worker privado quedó desplegado en la versión
`a347baa9-2a30-4b98-9bec-04c323c0b968`; tanto la consulta directa como la ruta
autenticada reconocen las dos tablas nuevas. La revisión no muta el `payload`
original ni activa geometrías o atributos del maestro. Las 41 pruebas
focalizadas cubren auditoría, permiso de evidencia para verificar, exclusión de
capas rechazadas, consulta por bbox, persistencia tras reinicio y transporte
D1. La aplicación también fue integrada en el checkout local que sirve
`D:/PROMETEO`.

## Trabajo local de títulos, notas, miniaturas y avance por plano (22/10/2026)

Preparado localmente, sin desplegar Django, Worker ni aplicar la migración
`007_plan_annotations.sql` a D1:

- Título administrativo editable por versión PDF o documento DWG, separado del
  nombre del original.
- Notas append-only con fecha, autor y revisión; agregar una nota no cambia el
  archivo ni activa datos.
- Miniatura privada de la primera página del PDF, con ampliación y acceso al
  original.
- Barra de once etapas por plano, derivada del mismo contrato que la ruta
  general; el respaldo queda fuera del conteo.
- Aviso explícito de aportes parciales: geometría, manzanas y numeración pueden
  proceder de PDF distintos y activarse por campos revisados.

La interfaz usa caché `v=4`. Las 52 pruebas focalizadas de Python, la prueba de
once etapas y el transporte D1 simulado pasan. La migración y publicación
permanecen pendientes de autorización.
