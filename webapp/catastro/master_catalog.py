"""Specialized incremental-catalog rows linked to immutable source versions."""
import json
import math
import re
import uuid

from .master_store import encoded, identifier, now


CATALOG_SECTIONS = (
    'attribute_definitions', 'administrative_areas', 'addresses', 'observations', 'identifiers', 'listings',
    'listing_observations', 'transactions', 'organizations', 'activities',
    'visits', 'developments', 'development_lots', 'development_stages',
    'environment_features', 'coverage_records',
)
REVIEW_TABLES = (
    'attribute_definitions', 'administrative_areas', 'addresses', 'property_observations',
    'external_identifiers', 'listings', 'listing_observations', 'transactions',
    'organizations', 'activities', 'visits', 'developments', 'development_lots',
    'development_stages', 'environment_features', 'coverage_records',
)
REVIEW_STATUSES = ('candidate', 'observed', 'verified', 'rejected', 'superseded', 'expired')
GEOMETRY_TYPES = {
    'Point', 'MultiPoint', 'LineString', 'MultiLineString',
    'Polygon', 'MultiPolygon', 'GeometryCollection',
}


def _rows(payload, name):
    value = payload.get(name, [])
    if not isinstance(value, list) or len(value) > 30000 or any(not isinstance(row, dict) for row in value):
        raise ValueError('Sección de catálogo no válida: ' + name)
    return value


def _text(value, label, required=False, limit=2000):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('Valor de texto no válido: ' + label)
    return value


def _number(value, label):
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Valor numérico no válido: ' + label)
    return value


def _target(value):
    return _text(value, 'target_ref', limit=300) if value is not None else None


def _generated(version_id, section, index, source_id=None):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, encoded(
        ['catastro-catalog', version_id, section, source_id if source_id is not None else index])))


def _stable(value, index):
    return identifier(value if value is not None else 'catalog-%s-%s' % ('item', index))


def _coordinate_pairs(value):
    if not isinstance(value, (list, tuple)):
        raise ValueError('Coordenadas geográficas no válidas.')
    if len(value) == 2 and all(type(item) in (int, float) and math.isfinite(item) for item in value):
        if not (-180 <= value[0] <= 180 and -90 <= value[1] <= 90):
            raise ValueError('Las coordenadas de entorno deben estar en WGS84.')
        yield value
        return
    for item in value:
        yield from _coordinate_pairs(item)


def _geometry(value):
    if not isinstance(value, dict) or value.get('type') not in GEOMETRY_TYPES:
        raise ValueError('La geometría debe ser una entidad GeoJSON admitida.')
    if value['type'] == 'GeometryCollection':
        geometries = value.get('geometries')
        if not isinstance(geometries, list) or len(geometries) > 1000:
            raise ValueError('La colección geométrica no es válida.')
        if not geometries:
            raise ValueError('La geometría no puede estar vacía.')
        for item in geometries:
            _geometry(item)
    else:
        pairs = list(_coordinate_pairs(value.get('coordinates')))
        if not pairs:
            raise ValueError('La geometría no puede estar vacía.')
    from shapely.geometry import shape
    shape_value = shape(value)
    if shape_value.is_empty or not shape_value.is_valid:
        raise ValueError('La geometría de entorno requiere revisión topológica.')
    return value


def _bounds(items):
    pairs = []
    for item in items:
        if item['type'] == 'GeometryCollection':
            pairs.extend(_bounds(item['geometries']))
        else:
            pairs.extend(_coordinate_pairs(item['coordinates']))
    return (min(point[0] for point in pairs), min(point[1] for point in pairs),
            max(point[0] for point in pairs), max(point[1] for point in pairs))


def _review_status(db, table, target_id, fallback=None):
    row = db.execute('SELECT status FROM catalog_review_status WHERE target_table=? AND target_id=?',
                     (table, target_id)).fetchone()
    return row[0] if row else fallback


def review(db, target_table, target_id, status, reason, evidence, actor, revision):
    """Append a review decision without rewriting the immutable source version."""
    if target_table not in REVIEW_TABLES:
        raise ValueError('Tipo de registro no revisable.')
    target_id = identifier(target_id, 'Identificador de registro')
    if status not in REVIEW_STATUSES:
        raise ValueError('Estado de revisión no válido.')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValueError('Describe el motivo de la revisión.')
    if evidence is None:
        evidence = {}
    if not isinstance(evidence, (dict, list)):
        raise ValueError('La evidencia debe ser un objeto o una lista.')
    if status == 'verified' and not evidence:
        raise ValueError('La verificación necesita evidencia identificable.')
    row = db.execute('SELECT source_version FROM ' + target_table + ' WHERE id=?', (target_id,)).fetchone()
    if not row or not row[0]:
        raise ValueError('El registro de catálogo no existe o no tiene una versión de origen.')
    source_version = row[0]
    columns = {item[1] for item in db.execute('PRAGMA table_info(' + target_table + ')')}
    original_status = None
    if 'status' in columns:
        prior = db.execute('SELECT status FROM ' + target_table + ' WHERE id=?', (target_id,)).fetchone()
        original_status = prior[0] if prior else None
    previous_status = _review_status(db, target_table, target_id, original_status)
    if previous_status == status:
        return {'target_table': target_table, 'target_id': target_id, 'status': status,
                'previous_status': previous_status, 'revision': revision, 'unchanged': True}
    if type(revision) is not int or revision < 1:
        raise ValueError('Revisión de catálogo no válida.')
    reviewed_at = now()
    evidence_json = encoded(evidence)
    db.execute('''INSERT OR REPLACE INTO catalog_review_status
        (target_table,target_id,status,revision,reviewed_at,actor,reason,evidence_json,source_version)
        VALUES (?,?,?,?,?,?,?,?,?)''',
               (target_table, target_id, status, revision, reviewed_at,
                str(actor)[:160], reason[:1000], evidence_json, source_version))
    db.execute('''INSERT INTO catalog_review_events
        (id,target_table,target_id,status,previous_status,revision,reviewed_at,actor,reason,evidence_json,source_version)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
               (str(uuid.uuid5(uuid.NAMESPACE_URL, encoded(
                   ['catastro-catalog-review', target_table, target_id, revision]))),
                target_table, target_id, status, previous_status, revision, reviewed_at,
                str(actor)[:160], reason[:1000], evidence_json, source_version))
    return {'target_table': target_table, 'target_id': target_id, 'status': status,
            'previous_status': previous_status, 'revision': revision, 'reviewed_at': reviewed_at}


def stage(db, version_id, district, source_date, payload):
    """Insert candidate catalog rows in the same transaction as their version."""
    known = {row[0] for row in db.execute('SELECT id FROM attribute_definitions')}
    maps = {}
    for index, row in enumerate(_rows(payload, 'attribute_definitions')):
        item_id = _stable(row.get('id'), index)
        value_type = row.get('value_type')
        if value_type not in ('text', 'number', 'boolean', 'date', 'json'):
            raise ValueError('Tipo de atributo no válido.')
        db.execute('INSERT OR IGNORE INTO attribute_definitions VALUES (?,?,?,?,?,?,?)', (
            item_id, _text(row.get('label'), 'label', True, 300), value_type,
            _text(row.get('unit'), 'unit', limit=50), _text(row.get('scope'), 'scope', True, 100),
            _text(row.get('description'), 'description', limit=2000), version_id))
        known.add(item_id)
    area_rows = _rows(payload, 'administrative_areas')
    maps['administrative_areas'] = {
        str(row.get('id', item_id)): item_id
        for index, row in enumerate(area_rows)
        for item_id in (_stable(row.get('id'), index),)
    }
    for index, row in enumerate(area_rows):
        item_id = _stable(row.get('id'), index)
        parent = row.get('parent_id')
        parent_id = maps['administrative_areas'].get(str(parent), str(parent)) if parent is not None else None
        db.execute('INSERT OR IGNORE INTO administrative_areas VALUES (?,?,?,?,?,?,?,?,?,?)', (
            item_id, parent_id, _text(row.get('kind'), 'administrative kind', True, 100),
            _text(row.get('code'), 'administrative code', limit=100),
            _text(row.get('code_scheme'), 'code_scheme', limit=100),
            _text(row.get('name'), 'administrative name', True, 500),
            _text(row.get('valid_from'), 'valid_from'), _text(row.get('valid_to'), 'valid_to'),
            version_id, encoded(row.get('details', {}))))
    for index, row in enumerate(_rows(payload, 'addresses')):
        db.execute('INSERT INTO addresses VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
            _generated(version_id, 'address', index, row.get('id')),
            row.get('entity_id'), _target(row.get('target_ref')),
            _text(row.get('address_type'), 'address_type', True, 100),
            _text(row.get('full_address'), 'full_address'), _text(row.get('street_type'), 'street_type', limit=100),
            _text(row.get('street_name'), 'street_name', limit=300),
            _text(row.get('municipal_number'), 'municipal_number', limit=100),
            _text(row.get('interior'), 'interior', limit=100), _text(row.get('postal_code'), 'postal_code', limit=20),
            _text(row.get('precision'), 'precision', limit=100),
            _text(row.get('status', 'candidate'), 'status', True, 50),
            version_id, encoded(row.get('evidence', {}))))
    maps['organizations'] = {}
    for index, row in enumerate(_rows(payload, 'organizations')):
        item_id = _stable(row.get('id'), index)
        maps['organizations'][str(row.get('id', item_id))] = item_id
        db.execute('INSERT OR IGNORE INTO organizations VALUES (?,?,?,?,?,?,?)', (
            item_id, _text(row.get('name'), 'organization name', True, 500),
            _text(row.get('organization_type'), 'organization_type', True, 100),
            _text(row.get('document_type'), 'document_type', limit=30),
            _text(row.get('document_number'), 'document_number', limit=100), version_id,
            encoded(row.get('details', {}))))
    maps['listings'] = {}
    for index, row in enumerate(_rows(payload, 'listings')):
        raw_id = row.get('id', index)
        item_id = _generated(version_id, 'listing', index, raw_id)
        maps['listings'][str(raw_id)] = item_id
        db.execute('INSERT INTO listings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
            item_id, row.get('entity_id'), _target(row.get('target_ref')),
            _text(row.get('portal'), 'portal', True, 100),
            _text(row.get('external_id'), 'external_id', True, 300),
            _text(row.get('url'), 'url', limit=2000), _text(row.get('operation'), 'operation', limit=100),
            _number(row.get('price'), 'price'), _text(row.get('currency'), 'currency', limit=10),
            _number(row.get('area_value'), 'area_value'), _text(row.get('area_unit'), 'area_unit', limit=20),
            _text(row.get('area_basis'), 'area_basis', limit=100),
            _text(row.get('status', 'active'), 'status', True, 50),
            _text(row.get('first_seen') or source_date, 'first_seen'),
            _text(row.get('last_seen') or source_date, 'last_seen'), version_id,
            encoded(row.get('details', {}))))
    for index, row in enumerate(_rows(payload, 'observations')):
        value_type = row.get('value_type')
        if value_type not in ('text', 'number', 'boolean', 'date', 'json'):
            raise ValueError('Tipo de observación no válido.')
        value = row.get('value')
        if value_type == 'text':
            value = _text(value, 'observation value')
        elif value_type == 'number':
            value = _number(value, 'observation value')
        elif value_type == 'boolean' and type(value) is not bool:
            raise ValueError('La observación booleana no es válida.')
        db.execute('INSERT INTO property_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
            _generated(version_id, 'observation', index, row.get('id')),
            row.get('entity_id'), _target(row.get('target_ref')),
            _text(row.get('namespace', 'general'), 'namespace', True, 100),
            _text(row.get('field_name'), 'field_name', True, 200), value_type,
            encoded(value), _text(row.get('unit'), 'unit', limit=50),
            _text(row.get('method'), 'method', limit=200), _text(row.get('status', 'candidate'), 'status', True, 50),
            _text(row.get('observed_at') or source_date, 'observed_at'),
            _text(row.get('valid_from'), 'valid_from'), _text(row.get('valid_to'), 'valid_to'),
            version_id, encoded(row.get('evidence', {}))))
    for index, row in enumerate(_rows(payload, 'identifiers')):
        db.execute('INSERT INTO external_identifiers VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
            _generated(version_id, 'identifier', index, row.get('id')),
            row.get('entity_id'), _target(row.get('target_ref')),
            _text(row.get('scheme'), 'scheme', True, 100),
            _text(row.get('value'), 'identifier value', True, 500),
            _text(row.get('authority'), 'authority', limit=300), _text(row.get('scope'), 'scope', limit=200),
            _text(row.get('status', 'candidate'), 'status', True, 50),
            _text(row.get('observed_at') or source_date, 'observed_at'), version_id,
            encoded(row.get('evidence', {}))))
    for index, row in enumerate(_rows(payload, 'listing_observations')):
        ref = str(row.get('listing_id') or row.get('listing_ref') or '')
        listing_id = maps['listings'].get(ref, ref)
        if not listing_id and row.get('portal') and row.get('external_id'):
            prior = db.execute('''SELECT l.id FROM listings l JOIN versions v ON v.id=l.source_version
                WHERE l.portal=? AND l.external_id=? ORDER BY v.created_at DESC LIMIT 1''',
                               (_text(row.get('portal'), 'portal', True, 100),
                                _text(row.get('external_id'), 'external_id', True, 300))).fetchone()
            listing_id = prior[0] if prior else None
        if listing_id and not maps['listings'].get(ref):
            existing = db.execute('SELECT 1 FROM listings WHERE id=?', (listing_id,)).fetchone()
            if not existing:
                listing_id = None
        if not listing_id:
            raise ValueError('La observación de anuncio necesita un listing_id existente o portal/external_id.')
        db.execute('INSERT INTO listing_observations VALUES (?,?,?,?,?,?,?,?,?)', (
            _generated(version_id, 'listing-observation', index, row.get('id')),
            listing_id, _text(row.get('observed_at') or source_date or now(), 'observed_at', True),
            _number(row.get('price'), 'price'), _text(row.get('currency'), 'currency', limit=10),
            _text(row.get('operation'), 'operation', limit=100),
            _text(row.get('status', 'observed'), 'status', True, 50),
            encoded(row.get('details', {})), version_id))
    for index, row in enumerate(_rows(payload, 'transactions')):
        db.execute('INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?)', (
            _generated(version_id, 'transaction', index, row.get('id')),
            row.get('entity_id'), _target(row.get('target_ref')),
            _text(row.get('transaction_type'), 'transaction_type', True, 100),
            _number(row.get('amount'), 'amount'), _text(row.get('currency'), 'currency', limit=10),
            _text(row.get('transaction_date'), 'transaction_date'), _text(row.get('recorded_date'), 'recorded_date'),
            version_id, encoded(row.get('evidence', {}))))
    for index, row in enumerate(_rows(payload, 'activities')):
        ref = row.get('organization_id')
        organization_id = maps['organizations'].get(str(ref), ref) if ref is not None else None
        db.execute('INSERT INTO activities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (
            _generated(version_id, 'activity', index, row.get('id')),
            row.get('entity_id'), _target(row.get('target_ref')), organization_id,
            _text(row.get('category'), 'category', limit=100), _text(row.get('subcategory'), 'subcategory', limit=100),
            _text(row.get('activity_name'), 'activity_name', limit=500),
            _text(row.get('ciiu_code'), 'ciiu_code', limit=20), _text(row.get('ciiu_version'), 'ciiu_version', limit=20),
            _text(row.get('valid_from'), 'valid_from'), _text(row.get('valid_to'), 'valid_to'),
            version_id, encoded(row.get('evidence', {}))))
    for index, row in enumerate(_rows(payload, 'visits')):
        db.execute('INSERT INTO visits VALUES (?,?,?,?,?,?,?,?)', (
            _generated(version_id, 'visit', index, row.get('id')),
            row.get('entity_id'), _target(row.get('target_ref')),
            _text(row.get('visited_at') or source_date, 'visited_at', True),
            _text(row.get('observer'), 'observer', limit=300), _text(row.get('summary'), 'summary'),
            version_id, encoded(row.get('details', {}))))
    maps['developments'] = {}
    for index, row in enumerate(_rows(payload, 'developments')):
        item_id = _stable(row.get('id'), index)
        maps['developments'][str(row.get('id', item_id))] = item_id
        developer_ref = row.get('developer_id')
        developer_id = maps['organizations'].get(str(developer_ref), developer_ref) if developer_ref is not None else None
        db.execute('INSERT OR IGNORE INTO developments VALUES (?,?,?,?,?,?,?,?)', (
            item_id, _text(row.get('name'), 'development name', True, 500), developer_id,
            _text(row.get('status'), 'development status', True, 100),
            _text(row.get('expected_start'), 'expected_start'), _text(row.get('expected_end'), 'expected_end'),
            version_id, encoded(row.get('details', {}))))
    for index, row in enumerate(_rows(payload, 'development_lots')):
        ref = str(row.get('development_id') or '')
        development_id = maps['developments'].get(ref, ref)
        if not development_id:
            raise ValueError('El vínculo de proyecto necesita development_id.')
        db.execute('INSERT INTO development_lots VALUES (?,?,?,?,?,?)', (
            _generated(version_id, 'development-lot', index, row.get('id')),
            development_id, row.get('entity_id'), _target(row.get('target_ref')),
            _text(row.get('role', 'related'), 'role', True, 100), version_id))
    for index, row in enumerate(_rows(payload, 'development_stages')):
        ref = str(row.get('development_id') or '')
        development_id = maps['developments'].get(ref, ref)
        if not development_id:
            raise ValueError('La etapa necesita development_id.')
        db.execute('INSERT INTO development_stages VALUES (?,?,?,?,?,?,?,?)', (
            _generated(version_id, 'development-stage', index, row.get('id')),
            development_id, _text(row.get('name'), 'stage name', True, 300),
            _text(row.get('status'), 'stage status', True, 100), _number(row.get('progress'), 'progress'),
            _text(row.get('observed_at') or source_date, 'observed_at', True),
            version_id, encoded(row.get('details', {}))))
    for index, row in enumerate(_rows(payload, 'environment_features')):
        geometry_value = row.get('geometry')
        if geometry_value is not None:
            _geometry(geometry_value)
        db.execute('INSERT INTO environment_features VALUES (?,?,?,?,?,?,?)', (
            _generated(version_id, 'environment', index, row.get('id')),
            _text(row.get('kind'), 'environment kind', True, 100), _text(row.get('name'), 'name', limit=500),
            district, encoded(geometry_value) if geometry_value is not None else None, version_id,
            encoded(row.get('evidence', {}))))
    for index, row in enumerate(_rows(payload, 'coverage_records')):
        db.execute('INSERT INTO coverage_records VALUES (?,?,?,?,?,?,?,?)', (
            _generated(version_id, 'coverage', index, row.get('id')),
            row.get('ubigeo') or district, _text(row.get('dataset'), 'dataset', True, 200),
            version_id, 1 if row.get('complete') else 0,
            int(_number(row.get('record_count', 0), 'record_count') or 0),
            _text(row.get('observed_at') or source_date or now(), 'observed_at', True),
            encoded(row.get('details', {}))))
    return len(_rows(payload, 'attribute_definitions')) + sum(
        len(_rows(payload, name)) for name in CATALOG_SECTIONS[1:])


def link(db, version_id):
    identities = {row['layer'] + ':' + row['source_feature_id']: row['entity_id']
                  for row in db.execute('SELECT layer,source_feature_id,entity_id FROM identities WHERE version_id=?',
                                        (version_id,))}
    for table in ('addresses', 'property_observations', 'external_identifiers', 'listings',
                  'transactions', 'activities', 'visits', 'development_lots'):
        for target, entity_id in identities.items():
            db.execute('UPDATE '+table+' SET entity_id=? WHERE source_version=? AND target_ref=? AND entity_id IS NULL',
                       (entity_id, version_id, target))


def for_entity(db, entity_id):
    queries = {
        'addresses': 'SELECT address_type,full_address,street_type,street_name,municipal_number,interior,postal_code,precision,status,source_version FROM addresses WHERE entity_id=? ORDER BY address_type',
        'observations': 'SELECT namespace,field_name,value_type,value_json,unit,method,status,observed_at,valid_from,valid_to,source_version FROM property_observations WHERE entity_id=? ORDER BY observed_at,id',
        'identifiers': 'SELECT scheme,value,authority,scope,status,observed_at,source_version FROM external_identifiers WHERE entity_id=? ORDER BY scheme,value',
        'listings': 'SELECT id,portal,external_id,url,operation,price,currency,area_value,area_unit,area_basis,status,first_seen,last_seen,source_version FROM listings WHERE entity_id=? ORDER BY last_seen DESC',
        'transactions': 'SELECT transaction_type,amount,currency,transaction_date,recorded_date,source_version FROM transactions WHERE entity_id=? ORDER BY transaction_date DESC',
        'activities': '''SELECT a.category,a.subcategory,a.activity_name,a.ciiu_code,a.ciiu_version,
            a.valid_from,a.valid_to,a.source_version,o.name AS organization_name,
            o.document_type AS organization_document_type,o.document_number AS organization_document_number
            FROM activities a LEFT JOIN organizations o ON o.id=a.organization_id
            WHERE a.entity_id=? ORDER BY a.valid_from DESC''',
        'visits': 'SELECT visited_at,observer,summary,details_json,source_version FROM visits WHERE entity_id=? ORDER BY visited_at DESC',
        'development_links': '''SELECT d.id,d.name,d.status,d.expected_start,d.expected_end,l.role,l.source_version
            FROM development_lots l JOIN developments d ON d.id=l.development_id WHERE l.entity_id=?''',
    }
    result = {}
    for name, sql in queries.items():
        rows = [dict(row) for row in db.execute(sql, (entity_id,))]
        for row in rows:
            for key in ('value_json', 'details_json'):
                if key in row:
                    row[key.removesuffix('_json')] = json.loads(row.pop(key))
        result[name] = rows
    listing_ids = [row['id'] for row in result['listings']]
    result['listing_history'] = []
    if listing_ids:
        placeholders = ','.join('?' for _ in listing_ids)
        result['listing_history'] = [dict(row) for row in db.execute(
            'SELECT listing_id,observed_at,price,currency,operation,status,details_json,source_version '
            'FROM listing_observations WHERE listing_id IN (' + placeholders + ') '
            'ORDER BY observed_at DESC', listing_ids)]
        for row in result['listing_history']:
            row['details'] = json.loads(row.pop('details_json'))
    return result


def search(db, filters=None):
    """Search candidate catalog records without changing their review state."""
    filters = filters or {}
    allowed = {'kind', 'ubigeo', 'portal', 'external_id', 'scheme', 'identifier_value',
               'category', 'ciiu_code', 'transaction_type', 'dataset', 'min_price',
               'max_price', 'status', 'review_status', 'environment_kind'}
    if set(filters) - allowed:
        raise ValueError('Filtro de catálogo no disponible.')
    kind = filters.get('kind') or ''
    results = []

    def common(entity_column, source_column, label_column, detail_column,
               date_column, amount_column='NULL', currency_column='NULL',
               status_column='NULL'):
        return (', '.join((
            entity_column + ' AS entity_id', source_column + ' AS source_version',
            label_column + ' AS label', detail_column + ' AS detail',
            date_column + ' AS observed_at', amount_column + ' AS amount',
            currency_column + ' AS currency', status_column + ' AS status')))

    def ubigeo_join(entity_column):
        return (' LEFT JOIN entities e ON e.id=' + entity_column +
                ' LEFT JOIN current_attributes a ON a.entity_id=' + entity_column)

    def review_join(table, alias):
        return (" LEFT JOIN catalog_review_status " + alias +
                " ON " + alias + ".target_table='" + table + "' AND " + alias + ".target_id=")

    def add_conditions(clauses, params, price=False):
        if filters.get('ubigeo'):
            clauses.append('e.ubigeo=?')
            params.append(str(filters['ubigeo']))
        if filters.get('status'):
            clauses.append('status=?')
            params.append(str(filters['status']))
        if price and filters.get('min_price') not in (None, ''):
            clauses.append('price>=?')
            params.append(_number(float(filters['min_price']), 'min_price'))
        if price and filters.get('max_price') not in (None, ''):
            clauses.append('price<=?')
            params.append(_number(float(filters['max_price']), 'max_price'))

    if not kind or kind == 'environment':
        clauses, params = [], []
        if filters.get('ubigeo'):
            clauses.append('f.ubigeo=?')
            params.append(str(filters['ubigeo']))
        if filters.get('environment_kind'):
            clauses.append('f.kind=?')
            params.append(str(filters['environment_kind']))
        if filters.get('review_status'):
            clauses.append("COALESCE(rs.status,'candidate')=?")
            params.append(str(filters['review_status']))
        results.extend(dict(row) for row in db.execute(
            "SELECT 'environment' AS kind,f.id,NULL AS entity_id,f.source_version,"
            "f.kind||' · '||COALESCE(f.name,'Sin nombre') AS label,"
            "json_extract(f.geometry_json,'$.type') AS detail,NULL AS observed_at,"
            "NULL AS amount,NULL AS currency,COALESCE(rs.status,'candidate') AS review_status,"
            "rs.reviewed_at,'environment_features' AS target_table FROM environment_features f" +
            review_join('environment_features', 'rs') + 'f.id WHERE ' +
            (' AND '.join(clauses) or '1=1') + ' ORDER BY f.kind,f.name LIMIT 500', params))
    if not kind or kind == 'listings':
        clauses, params = [], []
        if filters.get('ubigeo'):
            clauses.append('e.ubigeo=?')
            params.append(str(filters['ubigeo']))
        if filters.get('portal'):
            clauses.append('l.portal=?')
            params.append(str(filters['portal']))
        if filters.get('external_id'):
            clauses.append('l.external_id=?')
            params.append(str(filters['external_id']))
        if filters.get('status'):
            clauses.append('l.status=?')
            params.append(str(filters['status']))
        if filters.get('review_status'):
            clauses.append("COALESCE(rs.status,'candidate')=?")
            params.append(str(filters['review_status']))
        if filters.get('min_price') not in (None, ''):
            clauses.append('l.price>=?')
            params.append(_number(float(filters['min_price']), 'min_price'))
        if filters.get('max_price') not in (None, ''):
            clauses.append('l.price<=?')
            params.append(_number(float(filters['max_price']), 'max_price'))
        results.extend(dict(row) for row in db.execute(
            "SELECT 'listing' AS kind,l.id,l.entity_id,l.source_version,l.portal||' · '||l.external_id AS label,"
            "COALESCE(l.operation,'') AS detail,COALESCE(l.last_seen,l.first_seen) AS observed_at,"
            "l.price AS amount,l.currency AS currency,l.status AS status,"
            "COALESCE(rs.status,'candidate') AS review_status,rs.reviewed_at,"
            "'listings' AS target_table FROM listings l" + review_join('listings', 'rs') + 'l.id' +
            ubigeo_join('l.entity_id') + ' WHERE ' + (' AND '.join(clauses) or '1=1') +
            ' ORDER BY observed_at DESC LIMIT 500', params))
    if not kind or kind == 'identifiers':
        clauses, params = [], []
        if filters.get('ubigeo'):
            clauses.append('e.ubigeo=?')
            params.append(str(filters['ubigeo']))
        if filters.get('scheme'):
            clauses.append('i.scheme=?')
            params.append(str(filters['scheme']))
        if filters.get('identifier_value'):
            clauses.append('i.value=?')
            params.append(str(filters['identifier_value']))
        if filters.get('status'):
            clauses.append('i.status=?')
            params.append(str(filters['status']))
        if filters.get('review_status'):
            clauses.append("COALESCE(rs.status,'candidate')=?")
            params.append(str(filters['review_status']))
        results.extend(dict(row) for row in db.execute(
            "SELECT 'identifier' AS kind,i.id,i.entity_id,i.source_version,i.scheme||' · '||i.value AS label,"
            "i.authority AS detail,i.observed_at,NULL AS amount,NULL AS currency,i.status AS status,"
            "COALESCE(rs.status,'candidate') AS review_status,rs.reviewed_at,"
            "'external_identifiers' AS target_table FROM external_identifiers i" +
            review_join('external_identifiers', 'rs') + 'i.id' +
            ubigeo_join('i.entity_id') + ' WHERE ' +
            (' AND '.join(clauses) or '1=1') + ' ORDER BY label LIMIT 500', params))
    if not kind or kind == 'observations':
        clauses, params = [], []
        if filters.get('ubigeo'):
            clauses.append('e.ubigeo=?')
            params.append(str(filters['ubigeo']))
        if filters.get('status'):
            clauses.append('o.status=?')
            params.append(str(filters['status']))
        if filters.get('review_status'):
            clauses.append("COALESCE(rs.status,'candidate')=?")
            params.append(str(filters['review_status']))
        results.extend(dict(row) for row in db.execute(
            "SELECT 'observation' AS kind,o.id,o.entity_id,o.source_version,"
            "o.namespace||' · '||o.field_name AS label,o.value_json AS detail,o.observed_at,"
            "NULL AS amount,NULL AS currency,o.status AS status,"
            "COALESCE(rs.status,'candidate') AS review_status,rs.reviewed_at,"
            "'property_observations' AS target_table FROM property_observations o" +
            review_join('property_observations', 'rs') + 'o.id' +
            ubigeo_join('o.entity_id') + ' WHERE ' + (' AND '.join(clauses) or '1=1') +
            ' ORDER BY observed_at DESC LIMIT 500', params))
    if not kind or kind == 'transactions':
        clauses, params = [], []
        if filters.get('ubigeo'):
            clauses.append('e.ubigeo=?')
            params.append(str(filters['ubigeo']))
        if filters.get('transaction_type'):
            clauses.append('t.transaction_type=?')
            params.append(str(filters['transaction_type']))
        if filters.get('review_status'):
            clauses.append("COALESCE(rs.status,'candidate')=?")
            params.append(str(filters['review_status']))
        results.extend(dict(row) for row in db.execute(
            "SELECT 'transaction' AS kind,t.id,t.entity_id,t.source_version,t.transaction_type AS label,"
            "t.recorded_date AS detail,t.transaction_date AS observed_at,t.amount,t.currency,"
            "NULL AS status,COALESCE(rs.status,'candidate') AS review_status,rs.reviewed_at,"
            "'transactions' AS target_table FROM transactions t" +
            review_join('transactions', 'rs') + 't.id' +
            ubigeo_join('t.entity_id') + ' WHERE ' +
            (' AND '.join(clauses) or '1=1') + ' ORDER BY observed_at DESC LIMIT 500', params))
    if not kind or kind == 'activities':
        clauses, params = [], []
        if filters.get('ubigeo'):
            clauses.append('e.ubigeo=?')
            params.append(str(filters['ubigeo']))
        if filters.get('category'):
            clauses.append('p.category=?')
            params.append(str(filters['category']))
        if filters.get('ciiu_code'):
            clauses.append('p.ciiu_code=?')
            params.append(str(filters['ciiu_code']))
        if filters.get('review_status'):
            clauses.append("COALESCE(rs.status,'candidate')=?")
            params.append(str(filters['review_status']))
        results.extend(dict(row) for row in db.execute(
            "SELECT 'activity' AS kind,p.id,p.entity_id,p.source_version,"
            "COALESCE(NULLIF(p.activity_name,''),p.category,'Actividad') AS label,"
            "COALESCE(o.name,'') AS detail,p.valid_from AS observed_at,NULL AS amount,NULL AS currency,"
            "'candidate' AS status,COALESCE(rs.status,'candidate') AS review_status,"
            "rs.reviewed_at,'activities' AS target_table FROM activities p "
            "LEFT JOIN organizations o ON o.id=p.organization_id" +
            review_join('activities', 'rs') + 'p.id' +
            ubigeo_join('p.entity_id') + ' WHERE ' + (' AND '.join(clauses) or '1=1') +
            ' ORDER BY observed_at DESC LIMIT 500', params))
    if not kind or kind == 'coverage':
        clauses, params = [], []
        if filters.get('ubigeo'):
            clauses.append('c.ubigeo=?')
            params.append(str(filters['ubigeo']))
        if filters.get('dataset'):
            clauses.append('c.dataset=?')
            params.append(str(filters['dataset']))
        if filters.get('review_status'):
            clauses.append("COALESCE(rs.status,'candidate')=?")
            params.append(str(filters['review_status']))
        results.extend(dict(row) for row in db.execute(
            "SELECT 'coverage' AS kind,c.id,NULL AS entity_id,c.source_version,c.dataset AS label,"
            "CASE WHEN c.complete=1 THEN 'Completo' ELSE 'Parcial' END AS detail,c.observed_at,"
            "c.record_count AS amount,NULL AS currency,NULL AS status,"
            "COALESCE(rs.status,'candidate') AS review_status,rs.reviewed_at,"
            "'coverage_records' AS target_table FROM coverage_records c" +
            review_join('coverage_records', 'rs') + 'c.id WHERE ' +
            (' AND '.join(clauses) or '1=1') + ' ORDER BY observed_at DESC LIMIT 500', params))
    return results[:1000]


def review_history(db, target_table, target_id):
    if target_table not in REVIEW_TABLES:
        raise ValueError('Tipo de registro no revisable.')
    target_id = identifier(target_id, 'Identificador de registro')
    rows = []
    for row in db.execute(
            '''SELECT revision,status,previous_status,reviewed_at,actor,reason,evidence_json
               FROM catalog_review_events WHERE target_table=? AND target_id=?
               ORDER BY revision DESC LIMIT 200''', (target_table, target_id)):
        item = dict(row)
        item['evidence'] = json.loads(item.pop('evidence_json'))
        rows.append(item)
    return rows


def environment_collection(db, ubigeo, kinds=None, bbox=None, review_status=None, limit=2000):
    """Return private candidate environment vectors; no parcel identity is created."""
    from .master_contract import validate_field
    ubigeo = validate_field('ubigeo', ubigeo)
    if kinds is None:
        kinds = []
    if isinstance(kinds, str):
        kinds = [item for item in kinds.split(',') if item]
    if not isinstance(kinds, list) or len(kinds) > 50 or any(not isinstance(item, str) or len(item) > 100 for item in kinds):
        raise ValueError('Tipos de capa no válidos.')
    if bbox is not None:
        if (not isinstance(bbox, (list, tuple)) or len(bbox) != 4
                or any(type(value) not in (int, float) or not math.isfinite(value) for value in bbox)
                or not (-180 <= bbox[0] <= bbox[2] <= 180 and -90 <= bbox[1] <= bbox[3] <= 90)
                or bbox[0] == bbox[2] or bbox[1] == bbox[3]):
            raise ValueError('Extensión geográfica no válida.')
    if review_status is not None and review_status not in REVIEW_STATUSES:
        raise ValueError('Estado de revisión no válido.')
    if type(limit) is not int or not 1 <= limit <= 5000:
        raise ValueError('Límite de capa no válido.')
    clauses, params = ['f.ubigeo=?'], [ubigeo]
    if kinds:
        clauses.append('f.kind IN (' + ','.join('?' for _ in kinds) + ')')
        params.extend(kinds)
    if review_status:
        clauses.append("COALESCE(rs.status,'candidate')=?")
        params.append(review_status)
    else:
        clauses.append("COALESCE(rs.status,'candidate')<>'rejected'")
    rows = list(db.execute(
        '''SELECT f.id,f.kind,f.name,f.geometry_json,f.source_version,
                  COALESCE(rs.status,'candidate') AS review_status,rs.reviewed_at
           FROM environment_features f
           LEFT JOIN catalog_review_status rs
             ON rs.target_table='environment_features' AND rs.target_id=f.id
           WHERE ''' + ' AND '.join(clauses) + ' ORDER BY f.kind,f.id LIMIT ?',
        [*params, limit + 1]))
    features, invalid = [], 0
    for row in rows:
        if len(features) >= limit:
            break
        try:
            shape = json.loads(row['geometry_json']) if row['geometry_json'] else None
            if shape is None:
                invalid += 1
                continue
            _geometry(shape)
            if bbox is not None:
                west, south, east, north = _bounds([shape])
                if east < bbox[0] or west > bbox[2] or north < bbox[1] or south > bbox[3]:
                    continue
        except (TypeError, ValueError):
            invalid += 1
            continue
        features.append({
            'type': 'Feature', 'id': row['id'], 'geometry': shape,
            'properties': {'kind': row['kind'], 'name': row['name'],
                           'review_status': row['review_status'],
                           'reviewed_at': row['reviewed_at'],
                           'source_version': row['source_version']},
        })
    return {'type': 'FeatureCollection', 'crs': {'type': 'name', 'properties': {'name': 'EPSG:4326'}},
            'features': features, 'truncated': len(rows) > limit, 'invalid_geometries': invalid}
