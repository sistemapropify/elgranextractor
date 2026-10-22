"""Read-only description of the Catastro Maestro relational model.

This module does not inspect or mutate the master. It exposes the stable
identity path and the canonical lot query used by the administration UI.
"""

LOT_QUERY = """WITH active_geometry AS (
  SELECT s.entity_id,
         c.value_json    AS geometry_json,
         c.version_id    AS geometry_version_id,
         c.evidence_json AS geometry_evidence_json,
         v.source_id,
         v.label         AS source_version_label,
         v.original_name,
         v.original_sha256
  FROM selections s
  JOIN contributions c ON c.id = s.contribution_id
  JOIN versions v      ON v.id = c.version_id
  WHERE s.field = '$geometry'
),
identifiers AS (
  SELECT entity_id,
         json_group_array(json_object(
           'scheme', scheme, 'value', value, 'status', status,
           'authority', authority, 'source_version', source_version
         )) AS identifiers_json
  FROM external_identifiers
  WHERE entity_id IS NOT NULL
  GROUP BY entity_id
),
owners AS (
  SELECT r.entity_id,
         json_group_array(json_object(
           'person_id', p.id, 'name', p.name,
           'document_type', p.document_type,
           'document_number', p.document_number,
           'relationship', r.kind
         )) AS owners_json
  FROM relationships r
  JOIN people p ON p.id = r.person_id
  WHERE r.person_id IS NOT NULL
  GROUP BY r.entity_id
),
attachments AS (
  SELECT entity_id,
         json_group_array(json_object(
           'media_id', id, 'kind', kind, 'object_key', object_key,
           'sha256', sha256, 'observed_at', observed_at,
           'source_version', source_version, 'details', details_json
         )) AS media_json
  FROM media
  GROUP BY entity_id
)
SELECT
  e.id                 AS entity_id,
  i.version_id         AS source_version_id,
  i.source_feature_id  AS plan_lot_id,
  e.kind,
  e.ubigeo,
  ca.sector, ca.urbanization, ca.block, ca.lot,
  ca.address, ca.registry_entry_number, ca.cuc,
  ca.land_area, ca.built_area,
  ca.front, ca.back, ca.left, ca.right,
  ca.floors, ca.units, ca.cadastral_use,
  g.geometry_json,
  g.geometry_version_id,
  g.geometry_evidence_json,
  g.source_id          AS geometry_source_id,
  g.source_version_label,
  g.original_name,
  g.original_sha256,
  identifiers.identifiers_json,
  owners.owners_json,
  attachments.media_json
FROM identities i
JOIN entities e ON e.id = i.entity_id
LEFT JOIN current_attributes ca ON ca.entity_id = e.id
LEFT JOIN active_geometry g ON g.entity_id = e.id
LEFT JOIN identifiers ON identifiers.entity_id = e.id
LEFT JOIN owners ON owners.entity_id = e.id
LEFT JOIN attachments ON attachments.entity_id = e.id
WHERE i.layer = 'lote'
  AND i.source_feature_id = ?;
"""

GROUPS = (
    {
        'name': 'Identidad y procedencia',
        'purpose': 'Traducen cada elemento de un plano a una identidad estable y conservan qué versión aportó cada dato.',
        'tables': (
            {'name': 'entities', 'key': 'id', 'role': 'UUID interno e inmutable del lote, edificio o unidad.'},
            {'name': 'identities', 'key': 'version_id + layer + source_feature_id',
             'role': 'Puente entre el ID del plano y entities.id.'},
            {'name': 'contributions', 'key': 'id', 'role': 'Cada campo inmutable aportado por una fuente.'},
            {'name': 'selections', 'key': 'entity_id + field',
             'role': 'Aporte vigente elegido, incluida la geometría en $geometry.'},
            {'name': 'sources', 'key': 'id', 'role': 'Origen documental: COFOPRI, PDF, DWG u otro.'},
            {'name': 'versions', 'key': 'id', 'role': 'Versión inmutable, huella SHA-256 y original.'},
            {'name': 'projects', 'key': 'id', 'role': 'Ámbito de ensamblaje de láminas.'},
        ),
    },
    {
        'name': 'Ficha consultable del lote',
        'purpose': 'Proyección tipada e indexada de los campos activos; los valores originales siguen en contributions.',
        'tables': (
            {'name': 'current_attributes', 'key': 'entity_id',
             'role': 'Área, medidas, sector, manzana, lote, dirección, uso, registro, pisos y unidades.'},
            {'name': 'property_observations', 'key': 'id',
             'role': 'Observaciones adicionales con fecha, método, estado y evidencia.'},
            {'name': 'attribute_definitions', 'key': 'id',
             'role': 'Define atributos extensibles y su unidad.'},
            {'name': 'administrative_areas', 'key': 'id',
             'role': 'País, departamento, provincia y distrito versionados.'},
            {'name': 'addresses', 'key': 'id',
             'role': 'Varias direcciones precisas por inmueble.'},
        ),
    },
    {
        'name': 'Personas, documentos e imágenes',
        'purpose': 'Vincula titulares y archivos al mismo UUID sin duplicar el lote.',
        'tables': (
            {'name': 'people', 'key': 'id', 'role': 'Personas documentadas.'},
            {'name': 'relationships', 'key': 'id',
             'role': 'Titularidad, unidades, documentos y vínculos entre entidades.'},
            {'name': 'media', 'key': 'id',
             'role': 'PDF, fachadas, interiores, techos de dron y manifiestos; object_key en R2 y SHA-256.'},
            {'name': 'registral_acts', 'key': 'id',
             'role': 'Antecedentes registrales con oficina, partida y fecha.'},
            {'name': 'boundary_segments', 'key': 'id',
             'role': 'Frente, fondo, lados, longitudes y geometría de cada segmento.'},
        ),
    },
    {
        'name': 'Identificadores y mercado',
        'purpose': 'Mantiene códigos oficiales separados del UUID y agrega información de mercado versionada.',
        'tables': (
            {'name': 'external_identifiers', 'key': 'id',
             'role': 'CUC, partida, ID COFOPRI, referencia catastral y códigos municipales.'},
            {'name': 'listings', 'key': 'id', 'role': 'Anuncios vinculados al inmueble.'},
            {'name': 'listing_observations', 'key': 'id',
             'role': 'Historial de precio, operación y estado de cada anuncio.'},
            {'name': 'transactions', 'key': 'id',
             'role': 'Operaciones documentadas, separadas de precios de oferta.'},
        ),
    },
    {
        'name': 'Actores, proyectos y entorno',
        'purpose': 'Relaciona el lote con actividades, visitas, proyectos y capas territoriales.',
        'tables': (
            {'name': 'organizations', 'key': 'id', 'role': 'Empresas e instituciones.'},
            {'name': 'activities', 'key': 'id', 'role': 'Actividades económicas y CIIU versionado.'},
            {'name': 'visits', 'key': 'id', 'role': 'Visitas e inspecciones con evidencia.'},
            {'name': 'developments', 'key': 'id', 'role': 'Proyectos inmobiliarios.'},
            {'name': 'development_lots', 'key': 'id', 'role': 'Relación entre proyecto e inmueble.'},
            {'name': 'development_stages', 'key': 'id', 'role': 'Avance histórico de cada proyecto.'},
            {'name': 'environment_features', 'key': 'id',
             'role': 'Vías, parques, equipamientos, riesgos y otras capas no parcelarias.'},
            {'name': 'coverage_records', 'key': 'id', 'role': 'Cobertura observada por UBIGEO y dataset.'},
            {'name': 'zones', 'key': 'id', 'role': 'Zonas y ámbitos de análisis versionados.'},
        ),
    },
    {
        'name': 'Revisión y auditoría',
        'purpose': 'Explica quién cambió un estado, con qué evidencia y en qué revisión.',
        'tables': (
            {'name': 'catalog_review_status', 'key': 'target_table + target_id',
             'role': 'Estado vigente de revisión de un registro.'},
            {'name': 'catalog_review_events', 'key': 'id',
             'role': 'Historial append-only de revisiones.'},
            {'name': 'journal', 'key': 'revision',
             'role': 'Operaciones y respaldo lógico del maestro.'},
            {'name': 'master_operations', 'key': 'id',
             'role': 'Idempotencia de confirmaciones D1.'},
        ),
    },
)

RELATIONS = (
    {'left': 'versions.id', 'operator': '1 : N', 'right': 'identities.version_id',
     'meaning': 'Una versión puede contener muchos elementos identificados.'},
    {'left': 'identities.entity_id', 'operator': 'N : 1', 'right': 'entities.id',
     'meaning': 'Todo código de plano apunta al UUID estable del inmueble.'},
    {'left': 'entities.id', 'operator': '1 : N', 'right': 'contributions / selections',
     'meaning': 'Los aportes por campo se seleccionan para cada entidad.'},
    {'left': 'entities.id', 'operator': '1 : 1', 'right': 'current_attributes.entity_id',
     'meaning': 'Vista tipada de los valores vigentes para consultas rápidas.'},
    {'left': 'entities.id', 'operator': '1 : N', 'right': 'media.entity_id',
     'meaning': 'PDF, fachadas, interiores y fotos de techo se enlazan al lote correcto.'},
    {'left': 'entities.id', 'operator': '1 : N', 'right': 'relationships.entity_id → people.id',
     'meaning': 'Uno o varios titulares y vínculos documentados.'},
    {'left': 'entities.id', 'operator': '1 : N', 'right': 'external_identifiers.entity_id',
     'meaning': 'CUC, partida y códigos de origen viven separados del UUID.'},
)


def value():
    return {
        'identity': 'entities.id',
        'source_link': 'identities.source_feature_id',
        'geometry_link': "selections.field = '$geometry'",
        'groups': GROUPS,
        'relations': RELATIONS,
        'lot_query': LOT_QUERY,
    }
