"""Import archived formalization reports into current D1 master entities."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from . import master_contract
from . import master_store
from .cofopri_vector_migration import CURRENT_ATTRIBUTE_COLUMNS
from .storage import R2, StorageError


def _number(value):
    if value in (None, ''):
        return None
    try:
        number = float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _measurement(value):
    parts = [
        part.strip().replace(',', '.')
        for part in str(value or '').replace(';', ',').replace('|', ',').split(',')
        if part.strip()
    ]
    numbers = [_number(part) for part in parts]
    if not numbers or any(number is None for number in numbers):
        return None, []
    return round(sum(numbers), 4), numbers


def _detail_object_key(ubigeo, source, predio):
    return ('geollaqta/formalizacion/' + ubigeo + '/' + source + '/' +
            predio + '.json')


def _detail_fields(detail):
    mapping = (
        ('NOMPJV', 'urbanization'),
        ('SECTOR', 'sector'),
        ('MZNA', 'block'),
        ('LOTE', 'lot'),
        ('TIPO_USO', 'cadastral_use'),
        ('PM_AREPRE', 'land_area'),
        ('PM_LTEFRE', 'front'),
        ('PM_LTEDER', 'right'),
        ('PM_LTEIZQ', 'left'),
        ('PM_LTEFON', 'back'),
        ('EDI_PISO', 'floor'),
        ('EDI_DPTO', 'unit'),
        ('FECHA_TITULO', 'property_registration_date'),
    )
    fields = {}
    for source, target in mapping:
        value = detail.get(source)
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
        if value == '':
            continue
        if target in (
                'land_area', 'front', 'right', 'left', 'back'):
            value = _number(value)
        if value in (None, ''):
            continue
        try:
            fields[target] = master_contract.validate_field(target, value)
        except ValueError:
            continue
    return fields


def _blank(value):
    return value is None or (
        isinstance(value, str) and not value.strip()
    )


def _boundary_rows(detail, entity_id, version_id, observed_at):
    rows = []
    for side, label, measure in (
            ('front', 'FC_FRENTE', 'PM_LTEFRE'),
            ('right', 'FC_DERECHA', 'PM_LTEDER'),
            ('left', 'FC_IZQUIERDA', 'PM_LTEIZQ'),
            ('back', 'FC_FONDO', 'PM_LTEFON')):
        boundary = str(detail.get(label) or '').strip()
        raw_measure = str(detail.get(measure) or '').strip()
        length, segments = _measurement(raw_measure)
        if not boundary and length is None:
            continue
        rows.append([
            str(uuid.uuid5(uuid.NAMESPACE_URL, master_store.encoded([
                version_id, entity_id, 'boundary', side]))),
            entity_id,
            side,
            length,
            None,
            version_id,
            master_store.encoded({
                'boundary': boundary,
                'raw_measure': raw_measure,
                'segments_m': segments,
                'source': 'COFOPRI formalización',
                'observed_at': observed_at,
            }),
        ])
    return rows


def _registral_rows(detail, entity_id, version_id, observed_at):
    if not any(detail.get(key) not in (None, '') for key in (
            'FECHA_TITULO', 'ESTADO_TITULO', 'FI_EST_REGIS',
            'FI_ORIGEN', 'ULTIMA_ACTUALIZACION')):
        return []
    return [[
        str(uuid.uuid5(uuid.NAMESPACE_URL, master_store.encoded([
            version_id, entity_id, 'formalizacion']))),
        entity_id,
        'formalizacion',
        None,
        str(detail.get('FI_CODPRE') or '') or None,
        None,
        observed_at,
        version_id,
        master_store.encoded(detail),
    ]]


_CURSOR_PREFIX = 'catastro:formalization-detail:'


def _cursor_key(ubigeo, source):
    return _CURSOR_PREFIX + ubigeo + ':' + source + ':cursor'


def _read_meta(gateway, key):
    rows = gateway.read('SELECT value FROM meta WHERE key=?', [key])
    return str(rows[0]['value']) if rows else None


def _oversize(error):
    text = str(error)
    return any(marker in text for marker in (
        '12 MB', '413', 'overloaded', 'Divide la versión', 'excede los límites'))


def _commit_cursor(gateway, key, value, actor):
    """Persist the R2 continuation cursor as an idempotent D1 meta write."""
    created_at = master_store.now()
    for attempt in range(5):
        revision = gateway.revision()
        next_revision = revision + 1
        journal = [
            next_revision, 'migration_batch', str(actor)[:160],
            created_at, 'Avanzar cursor de importación formalizada.',
            master_store.encoded({'key': key, 'value': value}),
            '{}',
        ]
        try:
            gateway.call({
                'action': 'commit',
                'id': str(uuid.uuid4()),
                'revision': revision,
                'changes': [
                    {'table': 'meta', 'upserts': [[key, value]],
                     'deletes': []},
                    {'table': 'journal', 'upserts': [journal],
                     'deletes': []},
                    {'table': 'meta', 'upserts': [
                        ['revision', str(next_revision)]],
                     'deletes': []},
                ],
                'result': {'revision': next_revision, 'key': key},
            })
            return
        except master_store.Conflict:
            time.sleep(attempt + 1)
            if attempt == 4:
                raise


def _list_pending(ubigeo, source, lots, cloud, cursor):
    lots_by_predio = {
        str((lot.get('properties') or {}).get('ID_PREDIO_RPU')
            or lot.get('id') or ''): lot
        for lot in lots
    }
    prefix = ('geollaqta/formalizacion/' + ubigeo + '/' + source + '/')
    listed = cloud.list_objects(
        prefix, max_pages=100, start_after_key=(cursor or None))
    pending = []
    for item in listed['objects']:
        key = item['key']
        filename = key.rsplit('/', 1)[-1]
        predio = filename[:-5] if filename.endswith('.json') else ''
        lot = lots_by_predio.get(predio)
        if lot is None:
            continue
        pending.append((lot, predio, key))
    return pending, listed


def _read_records(pending, cloud, source):
    def read(item):
        lot, predio, key = item
        try:
            body, _ = cloud.get_manifest(key)
        except StorageError:
            raise
        detail = json.loads(body)
        if (detail.get('ID_PREDIO_RPU') != predio
                or detail.get('source') != source
                or detail.get('FORMALIZATION_DETAIL_STATUS') != 'available'):
            return None
        return (lot, detail, key, hashlib.sha256(body).hexdigest())

    with ThreadPoolExecutor(
            max_workers=max(1, min(6, len(pending))),
            thread_name_prefix='formalizacion-r2') as pool:
        return [
            value for value in pool.map(read, pending)
            if value is not None
        ]


def _commit_chunk(gateway, ubigeo, district, chunk, actor, created_at,
                  source_id, source_exists, cursor_key=None,
                  cursor_value=None):
    predios = [detail['ID_PREDIO_RPU'] for _, detail, _, _ in chunk]
    identity_lookup = gateway.read(
        '''SELECT DISTINCT i.source_feature_id,i.entity_id
           FROM identities i JOIN versions v ON v.id=i.version_id
           WHERE v.source_id=? AND i.layer='lote'
             AND i.source_feature_id IN
                 (SELECT value FROM json_each(?))''',
        ['cofopri-formalizacion-' + ubigeo,
         master_store.encoded(predios)],
    )
    entities = {
        str(row['source_feature_id']): str(row['entity_id'])
        for row in identity_lookup
    }
    chunk = [
        item for item in chunk
        if item[1]['ID_PREDIO_RPU'] in entities
    ]
    if not chunk:
        return {'records': 0, 'batches': [], 'source_exists': source_exists}
    digest = hashlib.sha256(json.dumps(
        [item[1] for item in chunk],
        ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()
    version_id = source_id + ':' + digest[:24]
    changes = []
    if not source_exists:
        changes.append({
            'table': 'sources',
            'upserts': [[
                source_id, None,
                'COFOPRI · Formalización · ' + district,
                ubigeo, None, 'contributing',
            ]],
            'deletes': [],
        })
    changes.append({
        'table': 'versions',
        'upserts': [[
            version_id, source_id,
            'Formalización · detalles · ' + digest[:10],
            None, 'EPSG:4326',
            master_store.encoded({
                'status': 'verified',
                'method': 'Reporte oficial COFOPRI archivado en R2.',
            }),
            'Formalización · ' + ubigeo,
            digest, digest, created_at, str(actor)[:160],
            master_store.encoded({
                'records': [item[1] for item in chunk],
            }),
        ]],
        'deletes': [],
    })
    contribution_rows = []
    selection_rows = []
    identity_upserts = []
    boundary_rows = []
    registral_rows = []
    updates = {}
    field_sources = dict((
        ('urbanization', 'NOMPJV'), ('block', 'MZNA'),
        ('lot', 'LOTE'), ('cadastral_use', 'TIPO_USO'),
        ('land_area', 'PM_AREPRE'), ('floor', 'EDI_PISO'),
        ('unit', 'EDI_DPTO'),
        ('property_registration_date', 'FECHA_TITULO'),
    ))
    for lot, detail, key, sha256 in chunk:
        predio = detail['ID_PREDIO_RPU']
        entity_id = entities[predio]
        identity_upserts.append([version_id, 'lote', predio, entity_id])
        fields = _detail_fields(detail)
        current = updates.setdefault(entity_id, {})
        for field, value in fields.items():
            contribution_id = str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                master_store.encoded([
                    version_id, entity_id, 'lote', field])))
            contribution_rows.append([
                contribution_id, version_id, predio, 'lote',
                field, master_store.encoded(value),
                master_store.encoded({
                    'source': 'COFOPRI formalización',
                    'object_key': key,
                    'sha256': sha256,
                    'field': field_sources.get(field),
                }),
            ])
            selection_rows.append([entity_id, field, contribution_id])
            current[field] = value
        for index, (raw_field, raw_value) in enumerate(detail.items()):
            if raw_value in (None, ''):
                continue
            contribution_id = str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                master_store.encoded([
                    version_id, entity_id, 'raw-formal', raw_field])))
            contribution_rows.append([
                contribution_id, version_id, predio, 'lote',
                '$raw:formal:%04d' % index,
                master_store.encoded({
                    'label': raw_field,
                    'value': raw_value,
                    'source': 'COFOPRI formalización',
                }),
                master_store.encoded({
                    'object_key': key,
                    'sha256': sha256,
                    'original_field': raw_field,
                }),
            ])
        boundary_rows.extend(_boundary_rows(
            detail, entity_id, version_id, created_at))
        registral_rows.extend(_registral_rows(
            detail, entity_id, version_id, created_at))
    if contribution_rows:
        changes.append({
            'table': 'contributions',
            'upserts': contribution_rows,
            'deletes': [],
        })
    if selection_rows:
        changes.append({
            'table': 'selections',
            'upserts': selection_rows,
            'deletes': [],
        })
    if identity_upserts:
        changes.append({
            'table': 'identities',
            'upserts': identity_upserts,
            'deletes': [],
        })
    if boundary_rows:
        changes.append({
            'table': 'boundary_segments',
            'upserts': boundary_rows,
            'deletes': [],
        })
    if registral_rows:
        changes.append({
            'table': 'registral_acts',
            'upserts': registral_rows,
            'deletes': [],
        })
    entity_ids = list(updates)
    current_rows = gateway.read(
        '''SELECT * FROM current_attributes
           WHERE entity_id IN (SELECT value FROM json_each(?))''',
        [master_store.encoded(entity_ids)],
    )
    current_by_entity = {
        str(row['entity_id']): dict(row) for row in current_rows
    }
    attribute_rows = []
    for entity_id in entity_ids:
        row = current_by_entity.get(entity_id, {'entity_id': entity_id})
        row = {
            column: (None if _blank(value) else value)
            for column, value in row.items()
        }
        for field, value in updates[entity_id].items():
            if _blank(row.get(field)):
                row[field] = value
        attribute_rows.append([
            row.get(column) for column in CURRENT_ATTRIBUTE_COLUMNS
        ])
    changes.append({
        'table': 'current_attributes',
        'upserts': attribute_rows,
        'deletes': [],
    })
    if cursor_key and cursor_value:
        changes.append({
            'table': 'meta',
            'upserts': [[cursor_key, cursor_value]],
            'deletes': [],
        })
    for attempt in range(5):
        revision = gateway.revision()
        next_revision = revision + 1
        journal = [
            next_revision, 'migration_batch', str(actor)[:160],
            created_at, 'Importar fichas formalizadas desde R2.',
            master_store.encoded({
                'scope_ubigeo': ubigeo,
                'version_id': version_id,
                'records': len(chunk),
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
                    'version_id': version_id,
                    'records': len(chunk),
                },
            })
            source_exists = True
            break
        except master_store.Conflict:
            time.sleep(attempt + 1)
            if attempt == 4:
                raise
    return {
        'records': len(chunk),
        'batches': [{
            'version_id': version_id,
            'revision': next_revision,
            'records': len(chunk),
        }],
        'source_exists': source_exists,
    }


def _process_chunk_adaptive(gateway, ubigeo, district, chunk, actor,
                            created_at, source_id, source_exists,
                            cursor_key):
    if not chunk:
        return {'records': 0, 'batches': []}, source_exists
    try:
        result = _commit_chunk(
            gateway, ubigeo, district, chunk, actor, created_at,
            source_id, source_exists, cursor_key=cursor_key,
            cursor_value=chunk[-1][2])
        return result, result['source_exists']
    except (StorageError, ValueError) as error:
        if not _oversize(error) or len(chunk) <= 1:
            raise
        middle = len(chunk) // 2
        left, left_exists = _process_chunk_adaptive(
            gateway, ubigeo, district, chunk[:middle], actor, created_at,
            source_id, source_exists, cursor_key)
        right, right_exists = _process_chunk_adaptive(
            gateway, ubigeo, district, chunk[middle:], actor, created_at,
            source_id, left_exists, cursor_key)
        return {
            'records': left['records'] + right['records'],
            'batches': left['batches'] + right['batches'],
        }, right_exists


def _migrate_source(gateway, ubigeo, district, lots, cloud, source,
                    batch_size, actor):
    cursor_key = _cursor_key(ubigeo, source)
    cursor = _read_meta(gateway, cursor_key) or ''
    if cursor == 'done':
        return {
            'source': source,
            'available': 0,
            'processed': 0,
            'batches': [],
        }
    source_id = 'cofopri-formalizacion-detalle-' + ubigeo
    source_exists = bool(gateway.read(
        'SELECT id FROM sources WHERE id=?', [source_id]))
    created_at = master_store.now()
    available = 0
    processed = 0
    batches = []
    while True:
        pending, listed = _list_pending(ubigeo, source, lots, cloud, cursor)
        records = _read_records(pending, cloud, source)
        available += len(records)
        for offset in range(0, len(records), batch_size):
            chunk = records[offset:offset + batch_size]
            result, source_exists = _process_chunk_adaptive(
                gateway, ubigeo, district, chunk, actor, created_at,
                source_id, source_exists, cursor_key)
            processed += result['records']
            batches.extend(result['batches'])
        if not listed['truncated']:
            _commit_cursor(gateway, cursor_key, 'done', actor)
            break
        cursor = listed['objects'][-1]['key']
        _commit_cursor(gateway, cursor_key, cursor, actor)
    return {
        'source': source,
        'available': available,
        'processed': processed,
        'batches': batches,
    }


def migrate_formalization_details(gateway, ubigeo, district, lots, cloud=None,
                                  batch_size=100, actor='formalizacion-d1',
                                  records=None):
    """Attach every archived formalization report to its current master lot."""
    cloud = cloud or R2(timeout=30)
    batch_size = max(1, min(int(batch_size), 100))
    if records is not None:
        records = list(records)
        if not records:
            return {'ubigeo': ubigeo, 'available': 0, 'processed': 0}
        source_id = 'cofopri-formalizacion-detalle-' + ubigeo
        source_exists = bool(gateway.read(
            'SELECT id FROM sources WHERE id=?', [source_id]))
        created_at = master_store.now()
        processed = 0
        batches = []
        for offset in range(0, len(records), batch_size):
            chunk = records[offset:offset + batch_size]
            result, source_exists = _process_chunk_adaptive(
                gateway, ubigeo, district, chunk, actor, created_at,
                source_id, source_exists, None)
            processed += result['records']
            batches.extend(result['batches'])
        return {
            'ubigeo': ubigeo,
            'district': district,
            'available': len(records),
            'processed': processed,
            'batches': batches,
        }
    results = [
        _migrate_source(gateway, ubigeo, district, lots, cloud, source,
                        batch_size, actor)
        for source in ('psad56', 'wgs84')
    ]
    return {
        'ubigeo': ubigeo,
        'district': district,
        'available': sum(result['available'] for result in results),
        'processed': sum(result['processed'] for result in results),
        'batches': [batch for result in results for batch in result['batches']],
        'sources': results,
    }
