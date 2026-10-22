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
        if not listing_id:
            raise ValueError('La observación de anuncio necesita listing_id.')
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
        if geometry_value is not None and not isinstance(geometry_value, (dict, list)):
            raise ValueError('Geometría ambiental no válida.')
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
               'max_price', 'status'}
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
        if filters.get('min_price') not in (None, ''):
            clauses.append('l.price>=?')
            params.append(_number(float(filters['min_price']), 'min_price'))
        if filters.get('max_price') not in (None, ''):
            clauses.append('l.price<=?')
            params.append(_number(float(filters['max_price']), 'max_price'))
        results.extend(dict(row) for row in db.execute(
            "SELECT 'listing' AS kind,l.id,l.entity_id,l.source_version,l.portal||' · '||l.external_id AS label,"
            "COALESCE(l.operation,'') AS detail,COALESCE(l.last_seen,l.first_seen) AS observed_at,"
            "l.price AS amount,l.currency AS currency,l.status AS status FROM listings l" +
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
        results.extend(dict(row) for row in db.execute(
            "SELECT 'identifier' AS kind,i.id,i.entity_id,i.source_version,i.scheme||' · '||i.value AS label,"
            "i.authority AS detail,i.observed_at,NULL AS amount,NULL AS currency,i.status AS status "
            "FROM external_identifiers i" + ubigeo_join('i.entity_id') + ' WHERE ' +
            (' AND '.join(clauses) or '1=1') + ' ORDER BY label LIMIT 500', params))
    if not kind or kind == 'observations':
        clauses, params = [], []
        if filters.get('ubigeo'):
            clauses.append('e.ubigeo=?')
            params.append(str(filters['ubigeo']))
        if filters.get('status'):
            clauses.append('o.status=?')
            params.append(str(filters['status']))
        results.extend(dict(row) for row in db.execute(
            "SELECT 'observation' AS kind,o.id,o.entity_id,o.source_version,"
            "o.namespace||' · '||o.field_name AS label,o.value_json AS detail,o.observed_at,"
            "NULL AS amount,NULL AS currency,o.status AS status FROM property_observations o" +
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
        results.extend(dict(row) for row in db.execute(
            "SELECT 'transaction' AS kind,t.id,t.entity_id,t.source_version,t.transaction_type AS label,"
            "t.recorded_date AS detail,t.transaction_date AS observed_at,t.amount,t.currency,"
            "NULL AS status FROM transactions t" + ubigeo_join('t.entity_id') + ' WHERE ' +
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
        results.extend(dict(row) for row in db.execute(
            "SELECT 'activity' AS kind,p.id,p.entity_id,p.source_version,"
            "COALESCE(NULLIF(p.activity_name,''),p.category,'Actividad') AS label,"
            "COALESCE(o.name,'') AS detail,p.valid_from AS observed_at,NULL AS amount,NULL AS currency,"
            "'candidate' AS status FROM activities p LEFT JOIN organizations o ON o.id=p.organization_id" +
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
        results.extend(dict(row) for row in db.execute(
            "SELECT 'coverage' AS kind,c.id,NULL AS entity_id,c.source_version,c.dataset AS label,"
            "CASE WHEN c.complete=1 THEN 'Completo' ELSE 'Parcial' END AS detail,c.observed_at,"
            "c.record_count AS amount,NULL AS currency,NULL AS status FROM coverage_records c WHERE " +
            (' AND '.join(clauses) or '1=1') + ' ORDER BY observed_at DESC LIMIT 500', params))
    return results[:1000]
