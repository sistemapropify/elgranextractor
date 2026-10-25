"""Backfill validated Geollaqta lot manifests from R2 into the Catastro Maestro."""
import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .master_d1 import D1Store
from .master_ingest import prepare
from .master_store import Conflict
from .storage import R2, StorageError

_lot_cache = {}
_lot_cache_lock = threading.RLock()


def lot_ids(ubigeo, cloud=None):
    if not re.fullmatch(r'[0-9]{6}', str(ubigeo)):
        raise ValueError('UBIGEO no válido.')
    cloud = cloud or R2()
    cache_key = str(ubigeo)
    if type(cloud).__name__ == 'R2':
        with _lot_cache_lock:
            saved = _lot_cache.get(cache_key)
            if saved and saved[0] > time.monotonic() - 60:
                return list(saved[1]), saved[2]
    listed = cloud.list_prefixes('geollaqta/' + ubigeo + '/')
    values = []
    for prefix in listed['prefixes']:
        value = prefix.rstrip('/').split('/')[-1]
        if re.fullmatch(ubigeo + r'[0-9]{8,12}', value):
            values.append(value)
    result = sorted(set(values))
    if type(cloud).__name__ == 'R2':
        with _lot_cache_lock:
            _lot_cache[cache_key] = (time.monotonic(), result, listed['truncated'])
    return result, listed['truncated']


def _manifest(cloud, ubigeo, lot_id):
    prefix = 'geollaqta/' + ubigeo + '/' + lot_id + '/'
    get_manifest = getattr(cloud, 'get_manifest', cloud.get)
    try:
        body, _ = get_manifest(prefix + 'datos.json')
    except StorageError as error:
        raise StorageError('Lote ' + lot_id + ': ' + str(error),
                           error.http_status) from None
    digest = hashlib.sha256(body).hexdigest()
    snapshot = prefix + 'datos-' + digest + '.json'
    try:
        stored, _ = get_manifest(snapshot)
        if hashlib.sha256(stored).hexdigest() != digest:
            raise StorageError('El respaldo inmutable del lote no coincide.')
    except StorageError as error:
        if error.http_status != 404:
            raise
        stored = body
        snapshot = prefix + 'datos.json'
    manifest = json.loads(stored)
    if manifest.get('lot_id') != lot_id or manifest.get('district_ubigeo') != ubigeo:
        raise ValueError('El manifiesto no corresponde al lote solicitado.')
    if manifest.get('extraction_revision', 0) < 2:
        raise ValueError('El manifiesto es anterior al formato catastral validado.')
    attrs = (manifest.get('feature') or {}).get('attributes') or {}
    geometry_lot = str(attrs.get('ID_LOTE') or '').strip()
    geometry_district = str(attrs.get('ID_DIST') or '').strip()
    if geometry_lot and geometry_lot != lot_id:
        raise ValueError('La geometría del manifiesto no corresponde al código del lote.')
    if geometry_district and geometry_district != ubigeo:
        raise ValueError('La geometría del manifiesto no corresponde al distrito.')
    return manifest, snapshot, digest


def _verified_payload(manifest, snapshot, digest):
    manifest = {**manifest, 'retrieved_at': _iso_timestamp(manifest.get('retrieved_at'))}
    payload = prepare(manifest, source_verified=True)
    # The immutable manifest remains in R2. Do not duplicate every raw OCR page
    # in D1; keep only normalized fields, links and provenance in the master.
    payload.pop('raw_fields', None)
    payload.pop('raw_gis_attributes', None)
    payload['version']['original'].update(
        object_key=snapshot, sha256=digest, archive_status='verified_r2')
    payload['media'].append({
        'kind': 'source_manifest',
        'target': 'lote:' + manifest['lot_id'],
        'object_key': snapshot,
        'sha256': digest,
        'source_url': (manifest.get('feature') or {}).get('attributes', {}).get('ID_LOTE'),
        'observed_at': manifest.get('retrieved_at'),
    })
    return payload


def merge_batch(ubigeo, manifests):
    if not manifests or len(manifests) > 200:
        raise ValueError('Cada tanda debe contener entre 1 y 200 lotes.')
    prepared = []
    for manifest, snapshot, digest in manifests:
        payload = _verified_payload(manifest, snapshot, digest)
        prepared.append(payload)
    fingerprints = sorted(
        [item['version']['original']['sha256'] for item in prepared])
    digest = hashlib.sha256('\n'.join(fingerprints).encode()).hexdigest()
    source_id = 'geollaqta-' + ubigeo
    dates = sorted((item.get('retrieved_at') for item in prepared if item.get('retrieved_at')),
                   key=str)
    merged = {
        'schema': 'catastro-maestro-v1',
        'source': {'id': source_id, 'name': 'Geollaqta · ' + ubigeo,
                   'ubigeo': ubigeo, 'role': 'candidate'},
        'version': {
            'id': source_id + ':' + digest[:32],
            'label': 'Tanda ' + prepared[0]['features'][0]['id'] + ' · ' + prepared[-1]['features'][0]['id'],
            'source_date': _source_date(dates[-1]) if dates else None,
            'crs': 'EPSG:4326',
            'georeferencing': {
                'status': 'verified',
                'method': 'Geometría catastral COFOPRI entregada en EPSG:4326.',
                'evidence': {'service': 'Catastro_PCDPI/MapServer', 'out_sr': 4326,
                             'source_manifest_digest': digest},
            },
            'original': {'name': 'Geollaqta manifests · ' + digest,
                         'canonical_sha256': digest,
                         'archive_status': 'source_manifests_verified_r2'},
        },
    }
    for key in ('features', 'people', 'relationships', 'media',
                'boundary_segments', 'registral_acts', 'warnings', 'missing'):
        merged[key] = [entry for item in prepared for entry in item.get(key, [])]
    merged['batch_lot_ids'] = [item['source']['id'].removeprefix('cofopri-')
                               for item in prepared]
    merged['source_manifest_sha256'] = digest
    merged['retrieved_at'] = dates[-1] if dates else None
    return merged


def _activate_payload(store, payload, ubigeo, actor):
    result = store.stage(payload, store.revision, actor)
    applied = []
    for kind in ('lote', 'unidad'):
        feature_ids = [
            str(item['id']) for item in payload['features']
            if item.get('kind') == kind
        ]
        if not feature_ids:
            continue
        chunk_size = 40 if kind == 'unidad' else len(feature_ids)
        for offset in range(0, len(feature_ids), chunk_size):
            chunk = feature_ids[offset:offset + chunk_size]
            scope = {'ubigeo': ubigeo, 'kind': kind}
            if kind == 'unidad':
                scope['source_feature_ids'] = chunk
            plan = {
                'revision': store.revision,
                'version_id': payload['version']['id'],
                'mode': 'fill',
                'scope': scope,
                'fields': [],
                'reason': 'Incorporar lote validado desde Geollaqta.',
            }
            preview = store.preview(plan)
            applied.append(store.apply(plan, preview['token'], actor))
    return {**result, 'applied': applied}


def stage_batch(store, cloud, ubigeo, selected, actor='sistema-geollaqta', activate=True):
    # Large manifests can reach hundreds of MB. Download them one at a time so
    # memory usage stays bounded even when the batch contains several big files.
    with ThreadPoolExecutor(max_workers=1) as pool:
        manifests = list(pool.map(lambda lot_id: _manifest(cloud, ubigeo, lot_id),
                                  selected))
    payload = merge_batch(ubigeo, manifests)
    if activate:
        result = _activate_payload(store, payload, ubigeo, actor)
    else:
        result = store.stage(payload, store.revision, actor)
    return {**result, 'activated': activate, 'lots': len(selected)}


def _existing_lots(store):
    sources = {row[0] for row in store.db.execute(
        "SELECT id FROM sources WHERE id LIKE 'cofopri-%'")}
    active = {row[0] for row in store.db.execute(
        "SELECT source_feature_id FROM identities WHERE layer='lote'")}
    return ({value.removeprefix('cofopri-') for value in sources}, active)


def backfill(store, ubigeo='040126', batch_size=50, start=0, count=None,
             actor='sistema-geollaqta', activate=True, cloud=None):
    if type(batch_size) is not int or not 20 <= batch_size <= 200:
        raise ValueError('El tamaño de tanda debe estar entre 20 y 200.')
    cloud = cloud or R2()
    ids, truncated = lot_ids(ubigeo, cloud)
    requested = ids[start:start + count if count is not None else None]
    existing, active = _existing_lots(store)
    upgrades = [value for value in requested if value in existing and value not in active]
    selected = [value for value in requested if value not in existing]
    results = []
    for lot_id in upgrades:
        manifest, snapshot, digest = _manifest(cloud, ubigeo, lot_id)
        payload = _verified_payload(manifest, snapshot, digest)
        for attempt in range(3):
            try:
                results.append({**_activate_payload(store, payload, ubigeo, actor),
                                'lots': 1})
                break
            except Conflict:
                if attempt == 2:
                    raise
                store.refresh()
    for offset in range(0, len(selected), batch_size):
        chunk = selected[offset:offset + batch_size]
        for attempt in range(3):
            try:
                results.append(stage_batch(store, cloud, ubigeo, chunk, actor, activate))
                break
            except Conflict:
                if attempt == 2:
                    raise
                store.refresh()
    return {'ubigeo': ubigeo, 'available_lots': len(ids), 'listing_truncated': truncated,
            'selected_lots': len(selected), 'existing_upgrades': len(upgrades),
            'already_active_skipped': len([value for value in requested if value in active]),
            'batches': results}


class ScopeCommitGateway:
    """Commit one isolated batch without reloading the whole district into RAM."""

    def __init__(self, remote):
        self.remote = remote
        self.current_revision = int(remote.revision())

    def revision(self):
        return self.current_revision

    def _meta(self):
        return [{'key': 'revision', 'value': str(self.current_revision)}]

    def read(self, sql, params=()):
        return self._meta() if re.search(r'\bFROM\s+meta\b', sql, re.I) else []

    def read_many(self, queries):
        return [self._meta() if re.search(r'\bFROM\s+meta\b', item['sql'], re.I) else []
                for item in queries]

    def call(self, payload):
        confirmed = self.remote.call(payload)
        result = confirmed.get('result') or {}
        if isinstance(result.get('revision'), int):
            self.current_revision = result['revision']
        else:
            self.current_revision = int(self.remote.revision())
        return confirmed


def linked_lot_ids(gateway, ubigeo):
    source_id = 'geollaqta-' + ubigeo
    rows = gateway.read(
        '''SELECT DISTINCT i.source_feature_id
           FROM identities i
           JOIN versions v ON v.id=i.version_id
           WHERE v.source_id=? AND i.layer='lote'
             AND EXISTS(SELECT 1 FROM selections s
                        WHERE s.entity_id=i.entity_id AND s.field='$geometry')''',
        [source_id])
    return {str(row['source_feature_id']) for row in rows}


def migration_status(gateway, ubigeo='040126', cloud=None):
    cloud = cloud or R2(timeout=20)
    ids, truncated = lot_ids(ubigeo, cloud)
    linked = linked_lot_ids(gateway, ubigeo)
    pending = sorted(set(ids) - linked)
    revision = None
    if ids:
        body, _ = cloud.get('geollaqta/' + ubigeo + '/' + ids[0] + '/datos.json')
        revision = json.loads(body).get('extraction_revision')
    return {
        'ubigeo': ubigeo,
        'source_lots': len(ids),
        'linked_lots': len(linked.intersection(ids)),
        'pending_lots': len(pending),
        'listing_truncated': truncated,
        'manifest_revision': revision,
        'source_format': 'JSON por lote + PDF/fotos',
        'destination': 'Cloudflare D1 · prometeo-catastro-maestro',
        'master_url': '/catastro/maestro/?ubigeo=' + ubigeo,
    }


def _source_date(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).date().isoformat()
    text = str(value or '')
    return text[:10] if text else None


def _iso_timestamp(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    return value


def migrate_pending(gateway, ubigeo='040126', limit=20, actor='sistema-geollaqta',
                    cloud=None):
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError('La tanda debe contener entre 1 y 50 lotes.')
    cloud = cloud or R2(timeout=20)
    ids, truncated = lot_ids(ubigeo, cloud)
    linked = linked_lot_ids(gateway, ubigeo)
    pending = sorted(set(ids) - linked)
    selected = pending[:limit]
    if not selected:
        return {**migration_status(gateway, ubigeo, cloud), 'processed_lots': 0,
                'remaining_lots': 0, 'done': True}
    result = None
    last_conflict = None
    for attempt in range(5):
        commit_gateway = ScopeCommitGateway(gateway)
        store = D1Store(gateway=commit_gateway, scope=ubigeo)
        try:
            result = stage_batch(store, cloud, ubigeo, selected, actor, activate=True)
            break
        except Conflict as error:
            last_conflict = error
            if attempt == 4:
                raise
            time.sleep(.25 * (attempt + 1))
        finally:
            store.db.close()
    if result is None:
        raise last_conflict or Conflict('No se pudo aplicar la tanda.')
    linked.update(selected)
    remaining = sorted(set(ids) - linked)
    return {
        'ubigeo': ubigeo,
        'source_lots': len(ids),
        'linked_lots': len(linked.intersection(ids)),
        'pending_lots': len(remaining),
        'processed_lots': len(selected),
        'remaining_lots': len(remaining),
        'listing_truncated': truncated,
        'batch_revision': result.get('revision'),
        'done': not remaining,
        'source_format': 'JSON por lote + PDF/fotos',
        'destination': 'Cloudflare D1 · prometeo-catastro-maestro',
        'master_url': '/catastro/maestro/?ubigeo=' + ubigeo,
    }
