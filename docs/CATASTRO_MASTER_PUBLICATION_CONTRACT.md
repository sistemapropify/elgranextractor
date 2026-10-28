# Contrato de publicación del Catastro Maestro

El Catastro Maestro es la única fuente de verdad del sistema. Las fuentes
externas, los PDF, los DWG, las fichas y las fotografías son orígenes que
alimentan sus capas; ninguna aplicación consumidora debe consultarlas
directamente.

## Capas independientes

Cada lote puede publicar por separado:

- geometría de lote, manzana o vía;
- atributos catastrales;
- titulares y derechos;
- unidades y fichas;
- reportes, documentos y fotografías;
- procedencia, faltantes y versión del archivo de origen.

La ausencia de una capa no bloquea las demás. Un lote sin normalización D1
puede seguir mostrando la geometría y el manifiesto durable de R2 que ya
pertenece al maestro.

## Lectura para aplicaciones

La ficha canónica se publica en:

`GET /catastro/api/maestro/lotes/<codigo_catastral>/ficha/`

El ACM usa el mismo contrato mediante su adaptador autenticado:

`GET /acm/catastro/lotes/<codigo_catastral>/`

La respuesta incluye `schema`, `lot_id`, `master_status`,
`master_revision`, `attributes`, `owners`, `units`, `media`, `gallery`,
`reports`, `provenance`, `missing` y la identidad maestra cuando existe.

`master_status` distingue:

- `normalized_d1`: registro normalizado y gobernado por D1;
- `archived_pending_d1`: capa archivada por el maestro, visible de forma
  independiente mientras termina su normalización.

## Actualización

Las lecturas D1 no se almacenan en caché de aplicación. Un cambio confirmado
en el Catastro Maestro aparece en el ACM y en cualquier consumidor nuevo en su
siguiente consulta. Las respuestas D1 se marcan `private, no-store` y exponen
`X-Catastro-Master-Revision`.

Los archivos de R2 son inmutables y se validan con SHA-256. Se pueden cachear
porque no representan el estado editable del maestro.

## Geometría

La configuración del ACM ya no publica el proveedor primario de GeoLlaqta.
Los distritos con vectores extraídos se sirven desde las capas archivadas del
Catastro Maestro mediante el contrato de radio de fuentes maestras. Los
dashboards que necesiten geometría deben usar esa misma configuración o el
endpoint canónico de la capa, nunca ArcGIS/COFOPRI en vivo.

## Regla para nuevas aplicaciones

Una aplicación nueva debe:

1. autenticarse y respetar los permisos del ACM;
2. consultar el contrato canónico del maestro;
3. conservar `entity_id`, `master_revision`, procedencia y faltantes;
4. guardar correcciones como contribuciones al maestro, no como fichas
   paralelas;
5. no guardar copias de campos normalizados como fuente propia.
