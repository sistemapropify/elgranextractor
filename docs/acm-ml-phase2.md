# Mercado y ACM: contexto espacial e identidad, fase 2

La fase 2 agrega contexto auditable a las candidatas de datos. No entrena un
modelo, no predice precios y no convierte anuncios en inmuebles certificados.
El ACM conserva su algoritmo.

## Superficies visibles

- **Control de datos → Contexto**: /ingestas/scraping/calidad/?tab=contexto.
  Presenta evaluación geográfica, versiones de microzona y coincidencias por revisar.
- **Mapa**: /cuadrantizacion/mapa/. Capas Candidatas, Referencias, Por revisar
  y Posibles duplicados, todas desmarcadas al abrir. Solo consultan el área visible.
  El filtro de tipo de propiedad actúa sobre el área ya cargada, sin volver a
  consultar el servidor. El límite de 2000 registros se indica cuando corresponde; ampliar el zoom permite
  inspeccionar un área menor. No representa el inventario total del mercado.
- Cada pin abre una ficha compacta con ID, portal, precisión, precio, superficies
  separadas, antigüedad, estado ML y microzona/versionado cuando estén disponibles.
  Desde allí se abre la publicación, el editor existente o el contexto de identidad.
- Guardar una corrección cierra la ficha ML anterior y consulta únicamente las
  capas ML activadas. Si el proceso aún no reevaluó el registro, se muestra el
  contexto pendiente que devuelve el servidor.

## Qué significa la información

**Exa** significa ubicación exacta declarada por la fuente; **Apx**, aproximada.
Ninguna certifica catastro, dirección, distrito o inmueble físico. La evidencia
conservada puede ser incompleta: ausencia de evidencia no equivale a verificación.
Las aproximadas permanecen como referencia.

Las microzonas reutilizan los polígonos guardados en cuadrantización y conservan
versiones. Cambios de observación, geometría o reglas requieren una nueva evaluación.
Límites, solapamientos y geometrías inválidas deben permanecer pendientes o en
revisión; no se resuelven escogiendo silenciosamente una zona.

Una coincidencia propone una revisión, con razones y regla. El puntaje ordena la
revisión y no es probabilidad. Identidad pendiente o decisión desactualizada no
autoriza agrupar, excluir anuncios, contar inmuebles únicos ni admitirlos como un
conjunto espacial certificado. La misma URL o ID identifica un anuncio, no catastro.
Las decisiones humanas conservan motivo y versión; no fusionan registros fuente.

## Integración y verificación

La capa consume GET /ingestas/scraping/ml/mapa/ con south, west, north, east y layers.
El enlace opcional ?ml_record=ID se envía como record; no activa capas y no
sustituye los parámetros de las capas de portales. ml_lat/ml_lng válidos dentro
del recuadro de Perú centran el mapa en ese registro, sin consultar datos todavía.
El endpoint debe autenticar, validar límites y devolver contexto consistente
con la última observación. La UI descarta respuestas atrasadas o de otra vista.

El editor emite scraped-property-saved únicamente tras guardar con éxito.
El contrato es CustomEvent con detail.id entero positivo. La capa no solicita
datos al recibirlo si sus cuatro controles están desmarcados.

Pruebas de UI: SDK temprano/tardío, cero solicitudes iniciales, límites geográficos,
cancelación, respuestas obsoletas, enlaces HTTP(S), edición y recarga de contexto.
Las pruebas Node no sustituyen verificación visual autenticada ni pruebas del
endpoint, migración y worker en SQL Server.

## Fases siguientes

Congelar un conjunto con identidad y contexto revisados; entrenar por tipo de
inmueble; evaluar con datos independientes y cortes temporales/espaciales; medir
error y aporte de cada lote antes de publicar modelos con versión y reversión.
Hasta entonces no hay precisión predictiva medida ni entrenamiento en curso.
