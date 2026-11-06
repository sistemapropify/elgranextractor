"""Directly commit complete archived Geollaqta manifests into D1."""
from __future__ import annotations

import hashlib
import json
import time
import uuid

from . import geollaqta_bulk
from . import master_store
from .master_ingest import prepare
from .cofopri_vector_migration import CURRENT_ATTRIBUTE_COLUMNS
from .storage import R2


def _uid(*parts):
    return str(uuid.uuid5(
        uuid.NAMESPACE_URL, master_store.encoded(list(parts))))


def _prepared(ubigeo, lot_ids, cloud):
    prepared = []
    for lot_id in lot_ids:
        manifest, snapshot, digest = geollaqta_bulk._manifest(
            cloud, ubigeo, lot_id)
        payload = prepare(manifest, source_verified=True)
        payload['version']['original'].update(
            object_key=snapshot,
            sha256=digest,
            archive_status='verified_r2',
        )
        payload['media'].append({
            'kind': 'source_manifest',
            'target': 'lote:' + manifest['lot_id'],
            'object_key': snapshot,
            'sha256': digest,
            'source_url': (
                manifest.get('feature') or {}).get(
                    'attributes', {}).get('ID_LOTE'),
            'observed_at': manifest.get('retrieved_at'),
        })
        prepared.append(payload)
    return prepared


def _merge_payloads(ubigeo, district, prepared):
    fingerprints = sorted(
        item['version']['original']['sha256'] for item in prepared)
    digest = hashlib.sha256(
        '\n'.join(fingerprints).encode()).hexdigest()
    source_id = 'geollaqta-' + ubigeo
    merged = {
        'schema': 'catastro-maestro-v1',
        'source': {
            'id': source_id,
            'name': 'Geollaqta · ' + district,
            'ubigeo': ubigeo,
            'role': 'contributing',
        },
        'version': {
            'id': source_id + ':' + digest[:32],
            'label': 'Expedientes ' + prepared[0]['features'][0]['id'] +
                     ' · ' + prepared[-1]['features'][0]['id'],
            'source_date': None,
            'crs': 'EPSG:4326',
            'georeferencing': {
                'status': 'verified',
                'method': 'Geometría y documentos COFOPRI archivados en R2.',
            },
            'original': {
                'name': 'Geollaqta manifests · ' + digest,
                'canonical_sha256': digest,
                'archive_status': 'source_manifests_verified_r2',
            },
        },
    }
    for key in (
            'features', 'people', 'relationships', 'media',
            'boundary_segments', 'registral_acts', 'warnings', 'missing',
            'raw_fields'):
        merged[key] = [
            entry for item in prepared for entry in item.get(key, [])
        ]
    return merged


def _existing_lots(gateway, ubigeo, lot_ids):
    encoded = master_store.encoded(lot_ids)
    sources = [
        'geollaqta-' + ubigeo,
        'cofopri-pcdpi-' + ubigeo,
        'cofopri-formalizacion-' + ubigeo,
    ]
    rows = gateway.read(
        '''SELECT i.source_feature_id,i.entity_id,v.source_id
           FROM identities i JOIN versions v ON v.id=i.version_id
           WHERE i.layer='lote'
             AND v.source_id IN (SELECT value FROM json_each(?))
             AND i.source_feature_id IN (SELECT value FROM json_each(?))
           ORDER BY CASE v.source_id
             WHEN ? THEN 0 WHEN ? THEN 1 ELSE 2 END,
             v.created_at DESC''',
        [master_store.encoded(sources), encoded, sources[0], sources[1]],
    )
    values = {}
    for row in rows:
        values.setdefault(
            str(row['source_feature_id']), str(row['entity_id']))
    return values


def migrate_manifests_direct(gateway, ubigeo, district, lot_ids,
                             cloud=None, actor='geollaqta-d1'):
    """Write normalized parcels, people, files and boundaries to D1."""
    lot_ids = list(dict.fromkeys(str(value) for value in lot_ids if value))
    if not lot_ids:
        return {'ubigeo': ubigeo, 'lots': 0, 'processed': 0}
    cloud = cloud or R2(timeout=30)
    prepared = _prepared(ubigeo, lot_ids, cloud)
    payload = _merge_payloads(ubigeo, district, prepared)
    source_id = payload['source']['id']
    version = payload['version']
    created_at = master_store.now()
    existing_lots = _existing_lots(gateway, ubigeo, lot_ids)

    entities = {}
    entity_rows = []
    contribution_rows = []
    identity_rows = []
    selection_rows = []
    identifier_rows = []
    relationship_rows = []
    people_rows = []
    media_rows = []
    boundary_rows = []
    registral_rows = []
    attributes = {}

    for feature in payload['features']:
        feature_id = str(feature['id'])
        kind = feature['kind']
        if kind == 'lote' and feature_id in existing_lots:
            entity_id = existing_lots[feature_id]
        else:
            entity_id = _uid(
                'catastro-maestro', 'PE', source_id, kind, feature_id)
        entities[kind + ':' + feature_id] = entity_id
        if feature_id not in existing_lots or kind != 'lote':
            entity_rows.append([
                entity_id, kind, 'PE', ubigeo, created_at])
        identity_rows.append([
            version['id'], kind, feature_id, entity_id])
        values = dict(feature.get('fields') or {})
        values.update({
            'country_code': 'PE',
            'ubigeo': ubigeo,
        })
        attributes.setdefault(entity_id, {}).update(values)
        for field, value in values.items():
            contribution_id = _uid(
                version['id'], kind, feature_id, field)
            contribution_rows.append([
                contribution_id, version['id'], feature_id, kind, field,
                master_store.encoded(value),
                master_store.encoded(
                    (feature.get('provenance') or {}).get(
                        field, {'status': 'source_observation'})),
            ])
            selection_rows.append([entity_id, field, contribution_id])
        if feature.get('geometry'):
            contribution_id = _uid(
                version['id'], kind, feature_id, '$geometry')
            contribution_rows.append([
                contribution_id, version['id'], feature_id, kind,
                '$geometry', master_store.encoded(feature['geometry']),
                master_store.encoded(
                    (feature.get('provenance') or {}).get(
                        '$geometry', {'status': 'source_observation'})),
            ])
            selection_rows.append([
                entity_id, '$geometry', contribution_id])
        cuc = values.get('cuc')
        if cuc:
            identifier_rows.append([
                _uid(version['id'], entity_id, 'COFOPRI_CUC', cuc),
                entity_id, kind + ':' + feature_id, 'COFOPRI_CUC',
                str(cuc), 'COFOPRI', None, 'candidate', created_at,
                version['id'],
                master_store.encoded({'status': 'candidate'}),
            ])

    entity_ids = list(attributes)
    existing_selections = gateway.read(
        '''SELECT entity_id,field FROM selections
           WHERE entity_id IN (SELECT value FROM json_each(?))''',
        [master_store.encoded(entity_ids)],
    )
    occupied = {
        (str(row['entity_id']), str(row['field']))
        for row in existing_selections
    }
    selection_rows = [
        row for row in selection_rows
        if (str(row[0]), str(row[1])) not in occupied
    ]
    current_rows = gateway.read(
        '''SELECT * FROM current_attributes
           WHERE entity_id IN (SELECT value FROM json_each(?))''',
        [master_store.encoded(entity_ids)],
    )
    current = {
        str(row['entity_id']): dict(row) for row in current_rows
    }

    for raw_index, raw in enumerate(payload.get('raw_fields') or []):
        record = str(raw.get('source_record_id') or '')
        raw_entity = (
            entities.get('unidad:' + record)
            or entities.get('registro_documental:' + record))
        if not raw_entity:
            continue
        for field_index, field in enumerate(raw.get('fields') or []):
            raw_name = '$raw:%06d:%05d' % (raw_index, field_index)
            contribution_rows.append([
                _uid(version['id'], raw_entity, raw_name),
                version['id'],
                record,
                'unidad',
                raw_name,
                master_store.encoded({
                    'label': field.get('label'),
                    'original_label': field.get('original_label'),
                    'number': field.get('number'),
                    'value': field.get('value'),
                    'value_status': field.get('value_status'),
                    'section': field.get('section'),
                    'source': field.get('source'),
                }),
                master_store.encoded({
                    key: field.get(key) for key in (
                        'filename', 'page', 'document_type',
                        'mapping_status')
                    if field.get(key) is not None
                }),
            ])

    for index, owner in enumerate(payload['people']):
        record = str(owner.get('source_record_id') or '')
        owner_entity = (
            entities.get('unidad:' + record)
            or entities.get('registro_documental:' + record))
        if not owner_entity or not owner.get('name'):
            continue
        document_type = owner.get('document_type')
        document_number = owner.get('document_number')
        aligned = (
            owner.get('row') is not None
            and not owner.get('relationship_status'))
        person_id = (
            _uid('person-document', document_type, document_number)
            if aligned and document_type and document_number
            else _uid('person-observation', version['id'], index))
        person_name = str(owner['name'])
        people_rows.append([
            person_id, person_name,
            document_type if aligned else None,
            document_number if aligned else None,
            version['id'],
        ])
        relationship_rows.append([
            _uid(version['id'], 'owner', index),
            owner_entity,
            None,
            person_id,
            'titular_segun_documento',
            master_store.encoded(owner),
            version['id'],
        ])

    for index, relation in enumerate(payload['relationships']):
        source_entity = entities.get(relation.get('from'))
        target_entity = entities.get(relation.get('to'))
        if source_entity and target_entity:
            relationship_rows.append([
                _uid(version['id'], 'relation', index),
                source_entity,
                target_entity,
                None,
                relation['kind'],
                master_store.encoded(relation),
                version['id'],
            ])

    for index, item in enumerate(payload['media']):
        entity_id = entities.get(item.get('target'))
        if entity_id and item.get('object_key') and item.get('kind'):
            media_rows.append([
                _uid(version['id'], 'media', index),
                entity_id,
                item['kind'],
                item['object_key'],
                item.get('sha256'),
                item.get('observed_at'),
                version['id'],
                master_store.encoded(item),
            ])

    for index, item in enumerate(payload['boundary_segments']):
        entity_id = entities.get(item.get('target'))
        if not entity_id:
            continue
        boundary_rows.append([
            _uid(version['id'], 'boundary', index),
            entity_id,
            item.get('side', 'unknown'),
            item.get('length_m'),
            master_store.encoded(item['geometry'])
            if item.get('geometry') is not None else None,
            version['id'],
            master_store.encoded(item.get('evidence', {})),
        ])

    for index, item in enumerate(payload['registral_acts']):
        entity_id = entities.get(item.get('target'))
        if entity_id and item.get('kind'):
            registral_rows.append([
                _uid(version['id'], 'registral-act', index),
                entity_id,
                item['kind'],
                item.get('registry_office'),
                item.get('registry_number'),
                item.get('registry_seat'),
                item.get('observed_at'),
                version['id'],
                master_store.encoded(item),
            ])

    attribute_rows = []
    for entity_id, values in attributes.items():
        row = current.get(entity_id, {'entity_id': entity_id})
        for field, value in values.items():
            if row.get(field) in (None, ''):
                row[field] = value
        attribute_rows.append([
            row.get(column) for column in CURRENT_ATTRIBUTE_COLUMNS
        ])

    source_exists = bool(gateway.read(
        'SELECT id FROM sources WHERE id=?', [source_id]))
    changes = []
    if not source_exists:
        changes.append({
            'table': 'sources',
            'upserts': [[
                source_id, None, payload['source']['name'], ubigeo,
                None, 'contributing',
            ]],
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
    for table, rows in (
            ('entities', entity_rows),
            ('contributions', contribution_rows),
            ('identities', identity_rows),
            ('selections', selection_rows),
            ('external_identifiers', identifier_rows),
            ('people', people_rows),
            ('relationships', relationship_rows),
            ('media', media_rows),
            ('boundary_segments', boundary_rows),
            ('registral_acts', registral_rows),
            ('current_attributes', attribute_rows)):
        if rows:
            changes.append({
                'table': table,
                'upserts': rows,
                'deletes': [],
            })
    for attempt in range(5):
        revision = gateway.revision()
        next_revision = revision + 1
        journal = [
            next_revision, 'migration_batch', str(actor)[:160],
            created_at, 'Importar expedientes COFOPRI completos.',
            master_store.encoded({
                'scope_ubigeo': ubigeo,
                'version_id': version['id'],
                'lots': len(lot_ids),
            }),
            '{}',
        ]
        try:
            gateway.call({
                'action': 'commit',
                'id': str(uuid.uuid4()),
                'revision': revision,
                'changes': [
                    *changes,
                    {'table': 'journal', 'upserts': [journal],
                     'deletes': []},
                    {'table': 'meta', 'upserts': [
                        ['revision', str(next_revision)]],
                     'deletes': []},
                ],
                'result': {
                    'revision': next_revision,
                    'version_id': version['id'],
                    'lots': len(lot_ids),
                },
            })
            break
        except master_store.Conflict:
            time.sleep(attempt + 1)
            if attempt == 4:
                raise
    return {
        'ubigeo': ubigeo,
        'district': district,
        'lots': len(lot_ids),
        'features': len(payload['features']),
        'people': len(payload['people']),
        'media': len(payload['media']),
        'boundary_segments': len(payload['boundary_segments']),
        'registral_acts': len(payload['registral_acts']),
        'revision': next_revision,
        'version_id': version['id'],
    }
