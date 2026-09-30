# Mercado y ACM: admisión de datos, fase 1

Esta entrega agrega seguimiento para futuros modelos. No reemplaza el algoritmo
ACM ni entrena un modelo. Los candidatos son registros de anuncios, todavía no
inmuebles físicos únicos certificados: deduplicación entre portales y microzonas
pertenecen a la fase 2.

## Acceso visible

- Menú **Mercado y ACM → Control de datos y ML**: `/acm/control/`.
- Calidad existente → **Candidatas para entrenamiento**:
  `/ingestas/scraping/calidad/?tab=entrenamiento`.
- Filtros por portal, tipo, distrito, precisión, estado, trabajo de origen y
  primera versión/cambios. Exportación CSV de la selección.
- Cada registro muestra ID interno, código del portal, versión, motivos,
  editor existente y su historial. El editor conserva el enlace al anuncio.
- Las cifras cuentan registros únicos por estado, no versiones ni inmuebles
  deduplicados. Una versión nueva puede pertenecer a un anuncio antiguo.
- Se muestra el estado real del proceso y de la migración. Los contadores se
  refrescan sin recargar la página ni cerrar un editor abierto.

## Datos y proceso

`MLObservation` conserva el contenido de entrada y diferencias entre versiones.
`MLCandidate` apunta a la última observación de cada registro.
`MLPipelineState` guarda avance del barrido y señal del proceso.
La migración `ingestas.0026_ml_candidates` es aditiva.

Al guardar una propiedad o su revisión manual, se compara una huella de campos
relevantes. Cambiar solo fechas de avistamiento no crea otra versión. Precio,
superficies, precisión, descripción, estado de publicación y exclusión manual
sí pueden crearla. La evaluación se procesa fuera de la petición web. Una
evaluación antigua nunca reemplaza el estado de una versión más reciente.

El evaluador reanuda desde SQL tras un reinicio. La conciliación recorre el
histórico por lotes y se repite diariamente: también recupera actualizaciones
hechas con SQL directo o `QuerySet.update()`, que no emiten señales Django.
Las fallas de captura se registran y no interrumpen el scraper. Después de tres
fallos de evaluación, el registro queda en Error, visible y reintentable.

Regla inicial `offer-exact-v1`: venta, tipo admitido, precio USD positivo,
superficies explícitas requeridas y coordenadas marcadas exactas dentro de un
recuadro de Perú. El recuadro no certifica distrito, microzona ni coordenada.
Casa requiere terreno y construcción; terreno requiere terreno; departamento
y oficina requieren construcción. Antigüedad desconocida no equivale a cero.
Precios solo en soles quedan por revisar hasta tener conversión documentada.
Ubicación aproximada, alquileres y tipos fuera del alcance quedan de referencia.
Los anuncios retirados conservan su valor histórico, sin asumir venta cerrada.

La prioridad del estado es exclusión humana, referencia, revisión, candidata.
Todos los motivos se conservan aunque el estado principal sea referencia.
Las observaciones originales no son modificadas por revisiones posteriores.

## Correcciones autorizadas

El normalizador y el evaluador completan antigüedad faltante solo con un dato
explícito o año de construcción inequívoco. Usa la fecha de extracción; no la
fecha de ejecución de una reparación. No confunde entrega/remodelación con
construcción ni resuelve evidencia contradictoria inventando una edad.
El historial existente `CambioPropiedadScraping` registra antes, después y
evidencia (`system:ml-age-v1`). Respeta campos protegidos y revisión correcta.
No cambia fechas de primera/última presencia, ausencia o retiro.
No hay correcciones masivas nuevas de coordenadas, precios o superficies en
esta entrega: requieren evidencia específica del portal, nunca la predicción
del futuro modelo como sustituto de los datos observados.

## Operación

`startup.sh` aplica las migraciones existentes e inicia un proceso independiente
con `python manage.py ml_candidates_worker`. Log:
`/home/LogFiles/ml-candidates.log`. Variable `ML_CANDIDATES_ENABLED=0` deshabilita
ese proceso, no el ACM. Si la migración falta, el proceso espera y la pantalla
informa de ello. Un primer barrido se ejecuta automáticamente por lotes de 50.

Mantenimiento:

```text
python manage.py migrate ingestas
python manage.py ml_candidates_worker --once --reconcile
python manage.py ml_candidates_worker --once --retry-errors
```

Antes de publicar: revisar el diff, aplicar la migración y comprobar señal del
proceso, avance del barrido y totales. La consulta de un panel no inicia
entrenamientos ni llamadas a un proveedor de IA.

## Comprobaciones

Pruebas de reglas, fechas históricas, conflictos, exclusión manual, campos
protegidos, reintentos, transacciones, reversión de valores, conciliación y
autenticación: `ingestas.tests.test_ml_candidates`.
El workflow de integración incluye esas pruebas en su SQL Server aislado.
La verificación SQL local usa tablas con nombres únicos, comprueba el esquema,
JSON, idempotencia y actualización del estado; impide escrituras en propiedades
originales y elimina sus tablas de prueba al finalizar.

## Siguientes fases

2. Identidad entre portales, cobertura, microzonas y evidencia GPS.
3. Conjunto congelado, entrenamiento por tipo y evaluación independiente.
4. Seguimiento del error y del aporte medido por lote, versiones de modelo y
   publicación/retroceso con trazabilidad.

Hasta esas fases no existe precisión medida, aporte al modelo ni entrenamiento
en curso. Ninguna cifra de candidatas debe presentarse como inmuebles listos
para entrenar un modelo espacial certificado.
