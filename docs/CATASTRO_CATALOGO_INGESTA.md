# Catastro Maestro: catálogo incremental e ingesta

Fecha: 22/10/2026.

El Catastro Maestro ya no requiere esperar una validación global antes de
registrar nuevas fuentes. Cada aporte entra como una versión inmutable y cada
registro conserva su fuente, fecha, evidencia y estado. La activación se hace
después mediante comparación y selección por campo o ámbito.

## Flujo

1. Registrar fuente y versión inmutable.
2. Guardar el original y su SHA256.
3. Normalizar el lote en JSON.
4. Registrar la versión candidata en D1.
5. Revisar correspondencias e importes.
6. Comparar campos, geometrías y vínculos.
7. Activar sólo el ámbito revisado.
8. Conservar historial y permitir reversión.

La falta de una validación global de Arequipa no bloquea las etapas anteriores.
La revisión tampoco requiere completar el distrito: se decide por registro y
queda auditada.

## Secciones del JSON

| Sección | Contenido |
|---|---|
| `features` | Lotes, manzanas, edificios, unidades, establecimientos y registros documentales con campos y geometría. |
| `attribute_definitions` | Catálogo extensible de atributos adicionales con tipo, unidad y ámbito. |
| `administrative_areas` | País, departamento, provincia, distrito, sector, urbanización y otras jerarquías versionadas. |
| `addresses` | Varias direcciones por entidad, tipo, precisión y estado. |
| `observations` | Observaciones tipadas no cubiertas por columnas frecuentes, con vigencia y método. |
| `identifiers` | CUC, referencia catastral, códigos COFOPRI/municipales y otros identificadores externos. |
| `listings` | Publicaciones y anuncios; precio, moneda, operación, área y estado. |
| `listing_observations` | Historial de cambios de una publicación. |
| `transactions` | Operaciones documentadas, separadas de ofertas. |
| `organizations` | Inmobiliarias, promotores, empresas y otras organizaciones. |
| `activities` | Actividad principal/secundaria, CIIU versionado, establecimiento y vigencia. |
| `visits` | Visitas, interiores, observaciones y evidencia. |
| `developments` | Proyectos inmobiliarios y promotor. |
| `development_lots` | Relación proyecto-lote/unidad. |
| `development_stages` | Etapas, estado observado y avance. |
| `environment_features` | Vías, parques, equipamientos, riesgos y otras capas geográficas. |
| `coverage_records` | Cobertura declarada por distrito y dataset, con conteo y fecha. |

## Reglas

- Un identificador de fuente no se presenta automáticamente como código oficial.
- Un precio publicado no es una transacción acreditada.
- Una actividad publicada no sobrescribe el uso catastral documentado.
- Una visita o foto de una unidad no describe automáticamente todo el edificio.
- Las observaciones llevan `status` (`candidate`, `observed`, `verified` o
  `rejected`) y evidencia.
- Las geometrías sin posición verificada permanecen candidatas.
- Los registros entran en D1, pero sólo la aplicación revisada crea selecciones
  activas.

## Ejemplo

```json
{
  "source": {
    "id": "registros-arequipa-001",
    "name": "Registros y publicaciones Arequipa",
    "ubigeo": "040101"
  },
  "version": {
    "id": "registros-arequipa-001-v1",
    "label": "Lote inicial",
    "source_date": "2026-10-22",
    "crs": "EPSG:4326",
    "georeferencing": {
      "status": "pending"
    }
  },
  "features": [
    {
      "id": "lot-1",
      "kind": "lote",
      "fields": {
        "department": "Arequipa",
        "province": "Arequipa",
        "district": "Arequipa",
        "ubigeo": "040101",
        "sector": "32",
        "block": "001",
        "lot": "010",
        "land_area": 120
      },
      "provenance": {
        "land_area": {
          "source": "ficha",
          "status": "source_observation"
        }
      }
    }
  ],
  "attribute_definitions": [
    {
      "id": "construction-material",
      "label": "Material de construcción",
      "value_type": "text",
      "scope": "edificio"
    }
  ],
  "administrative_areas": [
    {
      "id": "pe",
      "kind": "country",
      "code": "PE",
      "code_scheme": "ISO-3166-1",
      "name": "Perú"
    },
    {
      "id": "pe-04",
      "parent_id": "pe",
      "kind": "department",
      "code": "04",
      "code_scheme": "UBIGEO",
      "name": "Arequipa"
    }
  ],
  "addresses": [
    {
      "target_ref": "lote:lot-1",
      "address_type": "principal",
      "street_name": "Ejemplo",
      "municipal_number": "123",
      "precision": "municipal"
    }
  ],
  "identifiers": [
    {
      "target_ref": "lote:lot-1",
      "scheme": "registro-publico",
      "value": "P06144874",
      "status": "candidate"
    }
  ],
  "organizations": [
    {
      "id": "agency-1",
      "name": "Inmobiliaria ejemplo",
      "organization_type": "inmobiliaria",
      "document_type": "RUC",
      "document_number": "20123456789"
    }
  ],
  "listings": [
    {
      "id": "listing-1",
      "target_ref": "lote:lot-1",
      "portal": "portal-ejemplo",
      "external_id": "ABC123",
      "url": "https://example.invalid/ABC123",
      "operation": "venta",
      "price": 250000,
      "currency": "USD",
      "status": "active"
    }
  ],
  "listing_observations": [
    {
      "listing_id": "listing-1",
      "price": 245000,
      "currency": "USD",
      "operation": "venta",
      "status": "observed"
    }
  ],
  "activities": [
    {
      "target_ref": "lote:lot-1",
      "organization_id": "agency-1",
      "category": "inmobiliaria",
      "activity_name": "Oficina inmobiliaria",
      "ciiu_version": "Revisión 4"
    }
  ],
  "coverage_records": [
    {
      "dataset": "registros-publicos",
      "complete": false,
      "record_count": 1
    }
  ]
}
```

## Entrada por API

La ruta administrativa existente
`/catastro/api/maestro/composicion/?action=stage` acepta este objeto como
`payload`. La interfaz de fuentes permite cargarlo desde **Incorporar un aporte
ya normalizado**.

El origen y el manifiesto nunca se sobrescriben. Una corrección crea una nueva
versión.

## Importación progresiva

La pantalla **Fuentes y versiones** ofrece tres entradas:

- **Paquete JSON completo** para el contrato descrito en este documento.
- **GeoJSON** para una capa de entorno. Admite `Point`, `MultiPoint`,
  `LineString`, `MultiLineString`, `Polygon`, `MultiPolygon` y
  `GeometryCollection` en WGS84. Cada elemento necesita geometría y se registra
  como candidato; el tipo de capa se indica en la pantalla.
- **NDJSON** para una sola sección. Cada línea debe ser un objeto JSON. El
  máximo es 30.000 filas y 12 MB por tanda.

Cada carga crea una fuente y versión inmutables. Los datos de una tanda no se
activan ni se publican automáticamente.

## Revisión auditable

La migración `006_catalog_review.sql` agrega dos estructuras:

- `catalog_review_status` conserva el estado vigente de revisión de cada fila.
- `catalog_review_events` conserva cada decisión como evento append-only, con
  autor, motivo, evidencia y revisión del maestro.

Estados admitidos: `candidate`, `observed`, `verified`, `rejected`,
`superseded` y `expired`. `verified` exige evidencia no vacía. Cambiar el estado
de revisión no modifica la versión de origen ni activa contribuciones del
maestro. La API administrativa recibe:

```json
{
  "action": "catalog_review",
  "revision": 12,
  "target_table": "external_identifiers",
  "target_id": "identificador-generado",
  "status": "verified",
  "reason": "Cotejado con la ficha y su original",
  "evidence": {
    "document": "ficha",
    "page": 1
  }
}
```

Las capas se consultan en
`/catastro/api/maestro/composicion/?view=environment&ubigeo=040103`.
Admite `kind`, `review_status`, `bbox=oeste,sur,este,norte` y `limit` de hasta
5.000. Por defecto excluye geometrías rechazadas. El resultado es una
`FeatureCollection` privada para usuarios administradores.

El historial de una publicación puede llegar en una versión posterior sin
repetir el anuncio: `listing_observations` acepta `listing_id` del mismo lote o
la pareja `portal` + `external_id`, que resuelve la publicación ya registrada.
