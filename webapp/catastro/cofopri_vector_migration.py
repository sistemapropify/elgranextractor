"""Stage deduplicated COFOPRI formalization vectors through MasterStore."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from shapely.geometry import shape
from shapely.strtree import STRtree

from . import master_contract
from . import master_store
from . import vector_snapshots
from .storage import R2


SOURCE_PREFIX = 'cofopri-formalizacion-'
IDENTIFIER_SCHEME = 'COFOPRI_RPU'
CURRENT_ATTRIBUTE_COLUMNS = (
    'entity_id', 'country_code', 'ubigeo', 'postal_code', 'department',
    'province', 'district', 'zone', 'sector', 'urbanization', 'block',
    'lot', 'building', 'entrance', 'floor', 'unit', 'address',
    'address_block', 'address_lot', 'street_type', 'street_name',
    'municipal_number', 'condition', 'registry_office',
    'registry_entry_type', 'notary_name', 'notary_kardex', 'deed_date',
    'registry_folios', 'registry_seat', 'property_registration_date',
    'construction_declaration', 'construction_registration_seat',
    'construction_registration_date', 'cuc', 'cadastral_reference',
    'cadastral_use', 'observed_use', 'zoning', 'use_category',
    'business_category', 'business_subcategory', 'ciiu_code',
    'ciiu_version', 'commercial_name', 'registry_entry_number',
    'land_area', 'built_area', 'geometric_land_area', 'gis_land_area',
    'gis_built_area', 'front', 'back', 'left', 'right', 'perimeter',
    'bedrooms', 'bathrooms', 'half_bathrooms', 'parking_spaces',
    'floors', 'units', 'is_corner', 'is_through', 'faces_park',
)


def _text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text[:2000] if text else None


def _number(value):
    if value in (None, ''):
        return None
    try:
        number = float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _integer(value):
    number = _number(value)
    return int(number) if number is not None else None


def _source_date(value):
    if isinstance(value, (int, float)):
        try:
            stamp = value / 1000 if value > 10**11 else value
            return datetime.fromtimestamp(
                stamp, tz=timezone.utc).date().isoformat()
        except (ValueError, OverflowError, OSError):
            return None
    text = str(value or '').strip()
    return text[:10] if text else None


def merged_formalization_lots(ubigeo, cloud=None):
    """Prefer PSAD56 and fill missing fields/geometry from WGS84 by RPU."""
    cloud = cloud or R2(timeout=30)
    grouped = {}
    for source in ('psad56', 'wgs84'):
        try:
            features = vector_snapshots.read_snapshot(
                ubigeo, 'lotes', cloud=cloud, source=source)['features']
        except ValueError:
            features = []
        for feature in features:
            properties = feature.get('properties') or {}
            rpu = str(properties.get('ID_PREDIO_RPU') or '').strip()
            key = rpu or '%s-%s' % (source, feature.get('id'))
            if key not in grouped:
                grouped[key] = {'id': key, 'source': source,
                                'properties': dict(properties),
                                'geometry': feature.get('geometry')}
                continue
            item = grouped[key]
            for name, value in properties.items():
                if item['properties'].get(name) in (None, '') and value not in (None, ''):
                    item['properties'][name] = value
            if not item.get('geometry') and feature.get('geometry'):
                item['geometry'] = feature['geometry']
    return [grouped[key] for key in sorted(grouped)]


def _feature(lot, ubigeo, district):
    properties = lot['properties']
    rpu = str(properties.get('ID_PREDIO_RPU') or '').strip()
    values = {
        'country_code': 'PE',
        'ubigeo': ubigeo,
        'department': 'Arequipa',
        'province': 'Arequipa',
        'district': district,
        'urbanization': _text(properties.get('NOMPJV')),
        'sector': _text(properties.get('COD_SECT')),
        'block': _text(properties.get('COD_MZNA') or properties.get('NRO_MZNA')),
        'lot': _text(properties.get('COD_LOTE') or properties.get('NRO_LOTE')),
        'land_area': _number(properties.get('AREA_TER')),
        'built_area': _number(properties.get('AREA_CON')),
        'floors': _integer(properties.get('NIVELES')),
        'units': _integer(properties.get('NRO_UNIDADES')),
        'cadastral_use': _text(
            properties.get('TIPO_USO') or properties.get('TIP_USO')),
    }
    values = {
        key: master_contract.validate_field(key, value)
        for key, value in values.items()
        if value not in (None, '')
    }
    provenance = {
        key: {
            'source': 'COFOPRI ' + lot['source'].upper(),
            'status': 'source_observation',
            **({'rpu': rpu} if rpu else {}),
        }
        for key in values
    }
    feature = {
        'id': lot['id'],
        'kind': 'lote',
        'fields': values,
        'provenance': provenance,
    }
    if lot.get('geometry'):
        feature['geometry'] = lot['geometry']
        provenance['$geometry'] = {
            'source': 'COFOPRI ' + lot['source'].upper(),
            'status': 'reprojected_by_arcgis_to_wgs84',
            'source_crs': (
                'EPSG:4248' if lot['source'] == 'psad56'
                else 'EPSG:4326'),
            **({'rpu': rpu} if rpu else {}),
        }
    return feature


def batch_payload(ubigeo, district, lots, index):
    source_id = SOURCE_PREFIX + ubigeo
    features = [_feature(lot, ubigeo, district) for lot in lots]
    digest = hashlib.sha256(json.dumps(
        [(item['id'], item.get('geometry')) for item in features],
        ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()
    version_id = source_id + ':' + digest[:24]
    identifiers = [
        {
            'target_ref': 'lote:' + feature['id'],
            'scheme': IDENTIFIER_SCHEME,
            'value': feature['id'],
            'status': 'candidate',
            'authority': 'COFOPRI',
        }
        for feature in features
        if feature['id'].startswith('P')
    ]
    return {
        'schema': master_contract.VERSION,
        'source': {
            'id': source_id,
            'name': 'COFOPRI · Formalización · ' + district,
            'ubigeo': ubigeo,
            'role': 'candidate',
        },
        'version': {
            'id': version_id,
            'label': 'Formalización RPU · %s · %s · %s' % (
                index, feature_id(features) or digest[:12], digest[:10]),
            'source_date': _source_date(
                next((lot['properties'].get('FECH_TRAN')
                      for lot in lots
                      if lot['properties'].get('FECH_TRAN')), None)),
            'crs': 'EPSG:4326',
            'georeferencing': {
                'status': 'verified',
                'method': 'ArcGIS reproyectó PSAD56 o WGS84 a EPSG:4326.',
                'evidence': {
                    'service': 'FORMALIZACION_PSAD56 / FORMALIZACION_WGS84',
                    'out_sr': 4326,
                },
            },
            'original': {
                'name': 'Vectores formalizados · ' + ubigeo,
                'canonical_sha256': digest,
                'archive_status': 'verified_vector_snapshot_r2',
            },
        },
        'features': features,
        'identifiers': identifiers,
        'warnings': [],
        'missing': [],
    }


def feature_id(features):
    return features[0]['id'] if features else None


def migrate_district(store, ubigeo, district, batch_size=100, limit=None,
                     actor='cofopri-formalizacion', progress=None):
    lots = merged_formalization_lots(ubigeo)
    source_id = SOURCE_PREFIX + ubigeo
    with store.lock:
        linked = {
            str(row[0]) for row in store.db.execute(
                '''SELECT i.source_feature_id FROM identities i
                   JOIN versions v ON v.id=i.version_id
                   WHERE v.source_id=? AND i.layer='lote' ''',
                (source_id,))
        }
    available = len(lots)
    lots = [lot for lot in lots if str(lot['id']) not in linked]
    if limit is not None:
        lots = lots[:int(limit)]
    batches = []
    for offset in range(0, len(lots), batch_size):
        chunk = lots[offset:offset + batch_size]
        payload = batch_payload(
            ubigeo, district, chunk, offset // batch_size + 1)
        staged = store.stage(payload, store.revision, actor)
        plan = {
            'revision': store.revision,
            'version_id': staged['version_id'],
            'mode': 'fill',
            'scope': {'ubigeo': ubigeo, 'kind': 'lote'},
            'fields': [],
            'reason': 'Incorporar formalización COFOPRI deduplicada por RPU.',
        }
        preview = store.preview(plan)
        applied = store.apply(plan, preview['token'], actor)
        item = {
            'batch': offset // batch_size + 1,
            'features': len(chunk),
            'version_id': staged['version_id'],
            'revision': applied.get('revision'),
            'processed': min(offset + len(chunk), len(lots)),
            'total': len(lots),
            'remaining': max(0, len(lots) - offset - len(chunk)),
        }
        batches.append(item)
        if progress:
            progress(item)
    return {
        'ubigeo': ubigeo,
        'district': district,
        'available_unique_lots': available,
        'already_linked': len(linked),
        'unique_formalization_lots': len(lots),
        'batches': batches,
    }


def migrate_direct(gateway, ubigeo, district, batch_size=200, limit=None,
                   actor='cofopri-formalizacion', progress=None):
    """Commit vector batches directly through D1 without loading the district."""
    source_id = SOURCE_PREFIX + ubigeo
    lots = merged_formalization_lots(ubigeo)
    linked_rows = gateway.read(
        '''SELECT DISTINCT i.source_feature_id FROM identities i
           JOIN versions v ON v.id=i.version_id
           WHERE v.source_id=? AND i.layer='lote' ''',
        [source_id])
    linked = {str(row['source_feature_id']) for row in linked_rows}
    available = len(lots)
    lots = [lot for lot in lots if str(lot['id']) not in linked]
    if limit is not None:
        lots = lots[:int(limit)]
    if not lots:
        return {
            'ubigeo': ubigeo,
            'district': district,
            'available_unique_lots': available,
            'already_linked': len(linked),
            'unique_formalization_lots': 0,
            'batches': [],
            'direct': True,
        }
    columns = list(CURRENT_ATTRIBUTE_COLUMNS)
    source_exists = bool(gateway.read(
        'SELECT id FROM sources WHERE id=?', [source_id]))
    created_at = master_store.now()
    batches = []
    for offset in range(0, len(lots), batch_size):
        chunk = lots[offset:offset + batch_size]
        payload = batch_payload(
            ubigeo, district, chunk, offset // batch_size + 1)
        version = payload['version']
        changes = []
        if not source_exists:
            changes.append({
                'table': 'sources',
                'upserts': [[source_id, None, payload['source']['name'],
                             ubigeo, None, 'contributing']],
                'deletes': [],
            })
        changes.append({
            'table': 'versions',
            'upserts': [[
                version['id'], source_id, version['label'],
                version['source_date'], version['crs'],
                master_store.encoded(version['georeferencing']),
                version['original']['name'],
                version['original']['canonical_sha256'],
                version['original']['canonical_sha256'], created_at,
                str(actor)[:160], master_store.encoded(payload),
            ]],
            'deletes': [],
        })
        entity_rows, contribution_rows, identity_rows = [], [], []
        selection_rows, attribute_rows, identifier_rows = [], [], []
        for feature in payload['features']:
            feature_id = str(feature['id'])
            entity_id = str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                master_store.encoded([
                    'catastro-maestro', 'PE', source_id, 'lote', feature_id])))
            entity_rows.append([entity_id, 'lote', 'PE', ubigeo, created_at])
            attributes = {column: None for column in columns}
            attributes.update(feature.get('fields') or {})
            attributes['entity_id'] = entity_id
            attribute_rows.append([attributes.get(column) for column in columns])
            for field, value in (feature.get('fields') or {}).items():
                contribution_id = str(uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    master_store.encoded([
                        version['id'], 'lote', feature_id, field])))
                evidence = (feature.get('provenance') or {}).get(
                    field, {'status': 'source_observation'})
                contribution_rows.append([
                    contribution_id, version['id'], feature_id, 'lote',
                    field, master_store.encoded(value),
                    master_store.encoded(evidence)])
                selection_rows.append([entity_id, field, contribution_id])
            if feature.get('geometry'):
                contribution_id = str(uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    master_store.encoded([
                        version['id'], 'lote', feature_id, '$geometry'])))
                evidence = (feature.get('provenance') or {}).get(
                    '$geometry', {'status': 'source_observation'})
                contribution_rows.append([
                    contribution_id, version['id'], feature_id, 'lote',
                    '$geometry', master_store.encoded(feature['geometry']),
                    master_store.encoded(evidence)])
                selection_rows.append([entity_id, '$geometry', contribution_id])
            identity_rows.append([version['id'], 'lote', feature_id, entity_id])
            for identifier in payload.get('identifiers') or []:
                if identifier.get('target_ref') != 'lote:' + feature_id:
                    continue
                identifier_rows.append([
                    str(uuid.uuid5(uuid.NAMESPACE_URL, master_store.encoded([
                        version['id'], entity_id, identifier['scheme'],
                        identifier['value']]))),
                    entity_id, identifier['target_ref'], identifier['scheme'],
                    identifier['value'], identifier.get('authority'), None,
                    identifier.get('status') or 'candidate', created_at,
                    version['id'], master_store.encoded({
                        'status': identifier.get('status') or 'candidate'}),
                ])
        for table, rows in (
                ('entities', entity_rows),
                ('contributions', contribution_rows),
                ('identities', identity_rows),
                ('selections', selection_rows),
                ('current_attributes', attribute_rows),
                ('external_identifiers', identifier_rows)):
            if rows:
                changes.append({'table': table, 'upserts': rows, 'deletes': []})
        for attempt in range(5):
            revision = gateway.revision()
            next_revision = revision + 1
            journal = [
                next_revision, 'migration_batch', str(actor)[:160],
                created_at, 'Migrar formalización COFOPRI en tanda directa.',
                master_store.encoded({
                    'scope_ubigeo': ubigeo,
                    'version_id': version['id'],
                    'features': len(chunk),
                }),
                '{}',
            ]
            commit_changes = [
                *changes,
                {'table': 'journal', 'upserts': [journal], 'deletes': []},
                {'table': 'meta', 'upserts': [
                    ['revision', str(next_revision)]], 'deletes': []},
            ]
            try:
                gateway.call({
                    'action': 'commit',
                    'id': str(uuid.uuid4()),
                    'revision': revision,
                    'changes': commit_changes,
                    'result': {
                        'revision': next_revision,
                        'version_id': version['id'],
                        'features': len(chunk),
                    },
                })
                source_exists = True
                break
            except master_store.Conflict:
                if attempt == 4:
                    raise
        item = {
            'batch': offset // batch_size + 1,
            'features': len(chunk),
            'version_id': version['id'],
            'revision': next_revision,
            'processed': min(offset + len(chunk), len(lots)),
            'total': len(lots),
            'remaining': max(0, len(lots) - offset - len(chunk)),
        }
        batches.append(item)
        if progress:
            progress(item)
    return {
        'ubigeo': ubigeo,
        'district': district,
        'available_unique_lots': available,
        'already_linked': len(linked),
        'unique_formalization_lots': len(lots),
        'batches': batches,
        'direct': True,
    }


def _snapshot_feature(feature, ubigeo, district, source, layer):
    properties = feature.get('properties') or {}
    kind = {'lotes': 'lote', 'manzanas': 'manzana', 'vias': 'via'}[layer]
    if layer == 'lotes':
        feature_id = str(
            properties.get('ID_LOTE') or feature.get('id') or '').strip()
        fields = {
            'country_code': 'PE',
            'ubigeo': ubigeo,
            'department': 'Arequipa',
            'province': 'Arequipa',
            'district': district,
            'urbanization': _text(
                properties.get('NOMPJV') or properties.get('HAB_URBANA')),
            'sector': _text(properties.get('COD_SECT')),
            'block': _text(properties.get('COD_MZNA') or properties.get(
                'NRO_MZNA')),
            'lot': _text(properties.get('COD_LOTE') or properties.get(
                'NRO_LOTE')),
            'land_area': _number(properties.get('AREA_TER')),
            'built_area': _number(properties.get('AREA_CON')),
            'floors': _integer(properties.get('NIVELES')),
            'units': _integer(properties.get('NRO_UNIDADES')),
            'cadastral_use': _text(
                properties.get('TIPO_USO') or properties.get('TIP_USO')),
            'zoning': _text(properties.get('ZONIFICACION')),
        }
    elif layer == 'manzanas':
        feature_id = str(
            properties.get('ID_MZNA') or feature.get('id') or '').strip()
        fields = {
            'country_code': 'PE',
            'ubigeo': ubigeo,
            'department': 'Arequipa',
            'province': 'Arequipa',
            'district': district,
            'sector': _text(properties.get('COD_SECT')),
            'block': _text(properties.get('COD_MZNA') or properties.get(
                'NRO_MZNA')),
        }
    else:
        feature_id = str(feature.get('id') or '').strip()
        fields = {
            'country_code': 'PE',
            'ubigeo': ubigeo,
            'department': 'Arequipa',
            'province': 'Arequipa',
            'district': district,
            'street_type': _text(
                properties.get('TIPO_VIA') or properties.get('TIP_VIA')),
            'street_name': _text(
                properties.get('NOM_VIA') or properties.get('NOM_CALLE')),
        }
    fields = {
        key: master_contract.validate_field(key, value)
        for key, value in fields.items() if value not in (None, '')
    }
    provenance = {
        key: {
            'source': 'COFOPRI ' + source.upper(),
            'status': 'source_observation',
        }
        for key in fields
    }
    result = {
        'id': feature_id,
        'kind': kind,
        'fields': fields,
        'provenance': provenance,
    }
    if feature.get('geometry'):
        result['geometry'] = feature['geometry']
        provenance['$geometry'] = {
            'source': 'COFOPRI ' + source.upper(),
            'status': 'reprojected_by_arcgis_to_wgs84',
            'source_crs': 'EPSG:4248' if source == 'psad56' else 'EPSG:4326',
        }
    return result


def _snapshot_payload(ubigeo, district, source, layer, features, index):
    source_id = 'cofopri-%s-%s' % (source, ubigeo)
    items = [
        _snapshot_feature(feature, ubigeo, district, source, layer)
        for feature in features
    ]
    digest = hashlib.sha256(json.dumps(
        [(item['id'], item.get('geometry')) for item in items],
        ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()
    identifiers = []
    for item, raw in zip(items, features):
        properties = raw.get('properties') or {}
        if layer == 'lotes':
            value = str(properties.get('ID_PREDIO_RPU') or '').strip()
            scheme = IDENTIFIER_SCHEME
        elif layer == 'vias':
            value = str(properties.get('COD_VIA') or '').strip()
            scheme = 'COFOPRI_VIA'
        else:
            value = str(properties.get('ID_MZNA') or '').strip()
            scheme = 'COFOPRI_MANZANA'
        if value:
            identifiers.append({
                'target_ref': item['kind'] + ':' + item['id'],
                'scheme': scheme,
                'value': value,
                'status': 'candidate',
                'authority': 'COFOPRI',
            })
    version_id = source_id + ':' + digest[:24]
    return {
        'schema': master_contract.VERSION,
        'source': {
            'id': source_id,
            'name': 'COFOPRI · %s · %s · %s' % (
                source.upper(), layer, district),
            'ubigeo': ubigeo,
            'role': 'contributing',
        },
        'version': {
            'id': version_id,
            'label': '%s %s · %s · %s' % (
                layer, index, items[0]['id'] if items else '', digest[:10]),
            'source_date': None,
            'crs': 'EPSG:4326',
            'georeferencing': {
                'status': 'verified',
                'method': 'ArcGIS entregó la capa en EPSG:4326.',
                'evidence': {
                    'service': 'Catastro_PCDPI/MapServer',
                    'out_sr': 4326,
                },
            },
            'original': {
                'name': 'Capa %s · %s · %s' % (source, layer, ubigeo),
                'canonical_sha256': digest,
                'archive_status': 'verified_vector_snapshot_r2',
            },
        },
        'features': items,
        'identifiers': identifiers,
        'warnings': [],
        'missing': [],
    }


def migrate_snapshot_direct(gateway, ubigeo, district, source='pcdpi',
                            layer='lotes', batch_size=100, limit=None,
                            actor='cofopri-vector-import', progress=None,
                            cloud=None):
    """Commit any archived COFOPRI vector layer directly to D1."""
    source_id = 'cofopri-%s-%s' % (source, ubigeo)
    kind = {'lotes': 'lote', 'manzanas': 'manzana', 'vias': 'via'}[layer]
    collection = vector_snapshots.read_snapshot(
        ubigeo, layer, source=source, cloud=cloud)
    features = list(collection.get('features') or [])
    linked_rows = gateway.read(
        '''SELECT DISTINCT i.source_feature_id
           FROM identities i JOIN versions v ON v.id=i.version_id
           WHERE v.source_id=? AND i.layer=? ''',
        [source_id, kind],
    )
    linked = {str(row['source_feature_id']) for row in linked_rows}
    available = len(features)
    normalized = [
        (_snapshot_feature(feature, ubigeo, district, source, layer), feature)
        for feature in features
    ]
    pending = [
        (item, feature) for item, feature in normalized
        if str(item['id']) not in linked
    ]
    if limit is not None:
        pending = pending[:int(limit)]
    if not pending:
        return {
            'ubigeo': ubigeo, 'district': district, 'source': source,
            'layer': layer, 'available': available,
            'already_linked': len(linked), 'processed': 0,
            'batches': [],
        }
    source_exists = bool(gateway.read(
        'SELECT id FROM sources WHERE id=?', [source_id]))
    created_at = master_store.now()
    columns = list(CURRENT_ATTRIBUTE_COLUMNS)
    batches = []
    for offset in range(0, len(pending), batch_size):
        chunk = pending[offset:offset + batch_size]
        raw_features = [feature for _, feature in chunk]
        payload = _snapshot_payload(
            ubigeo, district, source, layer, raw_features,
            offset // batch_size + 1)
        version = payload['version']
        changes = []
        if not source_exists:
            changes.append({
                'table': 'sources',
                'upserts': [[source_id, None, payload['source']['name'],
                             ubigeo, None, 'contributing']],
                'deletes': [],
            })
        changes.append({
            'table': 'versions',
            'upserts': [[
                version['id'], source_id, version['label'],
                version['source_date'], version['crs'],
                master_store.encoded(version['georeferencing']),
                version['original']['name'],
                version['original']['canonical_sha256'],
                version['original']['canonical_sha256'], created_at,
                str(actor)[:160], master_store.encoded(payload),
            ]],
            'deletes': [],
        })
        entity_rows, contribution_rows, identity_rows = [], [], []
        selection_rows, attribute_rows, identifier_rows = [], [], []
        for feature in payload['features']:
            feature_id = str(feature['id'])
            entity_id = str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                master_store.encoded([
                    'catastro-maestro', 'PE', source_id, kind, feature_id])))
            entity_rows.append([entity_id, kind, 'PE', ubigeo, created_at])
            attributes = {column: None for column in columns}
            attributes.update(feature.get('fields') or {})
            attributes['entity_id'] = entity_id
            attribute_rows.append([
                attributes.get(column) for column in columns])
            for field, value in (feature.get('fields') or {}).items():
                contribution_id = str(uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    master_store.encoded([
                        version['id'], kind, feature_id, field])))
                contribution_rows.append([
                    contribution_id, version['id'], feature_id, kind,
                    field, master_store.encoded(value),
                    master_store.encoded({
                        k: v for k, v in (
                            feature.get('provenance') or {}).get(
                                field, {}).items()
                    }),
                ])
                selection_rows.append([
                    entity_id, field, contribution_id])
            if feature.get('geometry'):
                contribution_id = str(uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    master_store.encoded([
                        version['id'], kind, feature_id, '$geometry'])))
                contribution_rows.append([
                    contribution_id, version['id'], feature_id, kind,
                    '$geometry', master_store.encoded(feature['geometry']),
                    master_store.encoded(
                        feature.get('provenance', {}).get(
                            '$geometry', {})),
                ])
                selection_rows.append([
                    entity_id, '$geometry', contribution_id])
            identity_rows.append([
                version['id'], kind, feature_id, entity_id])
            for identifier in payload.get('identifiers') or []:
                if identifier.get('target_ref') != kind + ':' + feature_id:
                    continue
                identifier_rows.append([
                    str(uuid.uuid5(uuid.NAMESPACE_URL, master_store.encoded([
                        version['id'], entity_id, identifier['scheme'],
                        identifier['value']]))),
                    entity_id, identifier['target_ref'],
                    identifier['scheme'], identifier['value'],
                    identifier.get('authority'), None,
                    identifier.get('status') or 'candidate', created_at,
                    version['id'],
                    master_store.encoded({
                        'status': identifier.get('status') or 'candidate'}),
                ])
        for table, rows_for_table in (
                ('entities', entity_rows),
                ('contributions', contribution_rows),
                ('identities', identity_rows),
                ('selections', selection_rows),
                ('current_attributes', attribute_rows),
                ('external_identifiers', identifier_rows)):
            if rows_for_table:
                changes.append({
                    'table': table,
                    'upserts': rows_for_table,
                    'deletes': [],
                })
        for attempt in range(5):
            revision = gateway.revision()
            next_revision = revision + 1
            journal = [
                next_revision, 'migration_batch', str(actor)[:160],
                created_at, 'Importar capa COFOPRI desde R2.',
                master_store.encoded({
                    'scope_ubigeo': ubigeo,
                    'version_id': version['id'],
                    'features': len(chunk),
                    'layer': layer,
                }),
                '{}',
            ]
            commit_changes = [
                *changes,
                {'table': 'journal', 'upserts': [journal],
                 'deletes': []},
                {'table': 'meta', 'upserts': [
                    ['revision', str(next_revision)]], 'deletes': []},
            ]
            try:
                gateway.call({
                    'action': 'commit',
                    'id': str(uuid.uuid4()),
                    'revision': revision,
                    'changes': commit_changes,
                    'result': {
                        'revision': next_revision,
                        'version_id': version['id'],
                        'features': len(chunk),
                    },
                })
                source_exists = True
                break
            except master_store.Conflict:
                if attempt == 4:
                    raise
        item = {
            'batch': offset // batch_size + 1,
            'features': len(chunk),
            'source': source,
            'layer': layer,
            'revision': next_revision,
            'processed': min(offset + len(chunk), len(pending)),
            'total': len(pending),
            'remaining': max(0, len(pending) - offset - len(chunk)),
        }
        batches.append(item)
        if progress:
            progress(item)
    return {
        'ubigeo': ubigeo, 'district': district, 'source': source,
        'layer': layer, 'available': available,
        'already_linked': len(linked), 'processed': len(pending),
        'batches': batches,
    }


def _pcdpi_payload(ubigeo, district, matches, features, index):
    source_id = 'cofopri-pcdpi-' + ubigeo
    items = []
    identifiers = []
    for feature in features:
        properties = feature.get('properties') or {}
        lot_id = str(properties.get('ID_LOTE') or '').strip()
        if not lot_id:
            continue
        fields = {
            'country_code': 'PE',
            'ubigeo': ubigeo,
            'department': 'Arequipa',
            'province': 'Arequipa',
            'district': district,
            'sector': _text(properties.get('COD_SECT')),
            'block': _text(properties.get('COD_MZNA')),
            'lot': _text(properties.get('COD_LOTE')),
            'land_area': _number(properties.get('AREA_TER')),
            'built_area': _number(properties.get('AREA_CON')),
            'floors': _integer(properties.get('NIVELES')),
            'units': _integer(properties.get('NRO_UNIDADES')),
        }
        fields = {
            key: master_contract.validate_field(key, value)
            for key, value in fields.items() if value not in (None, '')
        }
        items.append({
            'id': lot_id,
            'kind': 'lote',
            'fields': fields,
            'geometry': feature.get('geometry'),
            'provenance': {
                key: {
                    'source': 'COFOPRI PCDPI',
                    'status': 'source_observation',
                }
                for key in [*fields, '$geometry']
            },
        })
        cuc = str(properties.get('CUC') or '').strip()
        if cuc:
            identifiers.append({
                'target_ref': 'lote:' + lot_id,
                'scheme': 'COFOPRI_CUC',
                'value': cuc,
                'status': 'candidate',
                'authority': 'COFOPRI',
            })
    digest = hashlib.sha256(json.dumps(
        [(item['id'], item.get('geometry')) for item in items],
        ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()
    version_id = source_id + ':' + digest[:24]
    payload = {
        'schema': master_contract.VERSION,
        'source': {
            'id': source_id,
            'name': 'COFOPRI · PCDPI · ' + district,
            'ubigeo': ubigeo,
            'role': 'candidate',
        },
        'version': {
            'id': version_id,
            'label': 'PCDPI · %s · %s' % (index, digest[:10]),
            'source_date': None,
            'crs': 'EPSG:4326',
            'georeferencing': {
                'status': 'verified',
                'method': 'COFOPRI PCDPI entregado por ArcGIS en EPSG:4326.',
                'evidence': {'service': 'Catastro_PCDPI/MapServer', 'out_sr': 4326},
            },
            'original': {
                'name': 'Vectores PCDPI · ' + ubigeo,
                'canonical_sha256': digest,
                'archive_status': 'verified_vector_snapshot_r2',
            },
        },
        'features': items,
        'identifiers': identifiers,
        'warnings': [],
        'missing': [],
    }
    return payload, matches


def augment_pcdpi_identities(store, ubigeo, district, cloud=None,
                             actor='cofopri-pcdpi-link'):
    """Link PCDPI codes to existing entities by block/lot and polygon overlap."""
    cloud = cloud or R2(timeout=30)
    try:
        pcdpi = vector_snapshots.read_snapshot(
            ubigeo, 'lotes', cloud=cloud, source='pcdpi')['features']
    except ValueError:
        return {'ubigeo': ubigeo, 'features': 0, 'linked': 0}
    current = store.collection(ubigeo, 'lote')['features']
    records = []
    for feature in current:
        try:
            geometry = shape(feature['geometry'])
        except (KeyError, TypeError, ValueError):
            continue
        if geometry.is_empty or not geometry.is_valid:
            continue
        properties = feature.get('properties') or {}
        records.append({
            'id': feature['id'],
            'block': str(properties.get('block') or '').strip().lstrip('0').upper(),
            'lot': str(properties.get('lot') or '').strip().lstrip('0').upper(),
            'geometry': geometry,
            'centroid': geometry.centroid,
        })
    if not records:
        return {'ubigeo': ubigeo, 'features': len(pcdpi), 'linked': 0}
    tree = STRtree([record['centroid'] for record in records])
    matches = {}
    for feature in pcdpi:
        properties = feature.get('properties') or {}
        lot_id = str(properties.get('ID_LOTE') or '').strip()
        if not lot_id:
            continue
        block = str(properties.get('COD_MZNA') or '').strip().lstrip('0').upper()
        lot = str(properties.get('COD_LOTE') or '').strip().lstrip('0').upper()
        try:
            source_geometry = shape(feature['geometry'])
        except (KeyError, TypeError, ValueError):
            continue
        center = source_geometry.centroid
        best = None
        for candidate_index in tree.query(center.buffer(.0008)):
            candidate = records[int(candidate_index)]
            same_parcel = candidate['block'] == block and candidate['lot'] == lot
            if same_parcel and center.distance(candidate['centroid']) <= .0008:
                best = (2.0, candidate)
                break
            intersection = source_geometry.intersection(
                candidate['geometry']).area
            smaller = min(source_geometry.area, candidate['geometry'].area)
            if smaller and intersection / smaller >= .7:
                score = intersection / smaller
                if best is None or score > best[0]:
                    best = (score, candidate)
        if best:
            matches[lot_id] = best[1]['id']
    if not matches:
        return {'ubigeo': ubigeo, 'features': len(pcdpi), 'linked': 0}
    payload, _ = _pcdpi_payload(
        ubigeo, district, matches, pcdpi, 1)
    staged = store.stage(payload, store.revision, actor)
    identity_map = {'lote:' + lot_id: entity_id
                    for lot_id, entity_id in matches.items()}
    plan = {
        'revision': store.revision,
        'version_id': staged['version_id'],
        'mode': 'fill',
        'scope': {'ubigeo': ubigeo, 'kind': 'lote'},
        'fields': [],
        'identity_map': identity_map,
        'reason': 'Vincular códigos PCDPI con las entidades formalizadas.',
    }
    preview = store.preview(plan)
    applied = store.apply(plan, preview['token'], actor)
    return {
        'ubigeo': ubigeo,
        'features': len(pcdpi),
        'linked': len(matches),
        'revision': applied.get('revision'),
        'version_id': staged['version_id'],
    }
