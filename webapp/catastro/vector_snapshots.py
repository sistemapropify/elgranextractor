"""Independent district/layer vector snapshots stored outside primary services."""
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, build_opener

from django.core.cache import cache

from .storage import R2, StorageError

PREFIX = 'geollaqta/vectores/'
INDEX_KEY = PREFIX + 'index.json'
LAYERS = ('lotes', 'manzanas', 'vias')
LOCAL_INDEX = Path(__file__).with_name('data') / 'geollaqta-vector-index.json'
ROAD_TYPES = {
    '1': 'Avenida', '2': 'Calle', '3': 'Jirón', '4': 'Pasaje',
    '7': 'Prolongación', '13': 'Callejón',
}


class WorkerVectorStorage:
    """Read vector parts through the private Cloudflare Worker."""

    def __init__(self):
        from .master_d1 import configuration
        from .storage import NoRedirect
        self.url, self.token = configuration()
        self.opener = build_opener(NoRedirect())

    def get_manifest(self, key):
        request = Request(
            self.url + '/v1/vector-object?key=' + quote(key, safe=''),
            headers={'Authorization': 'Bearer ' + self.token,
                     'Accept': 'application/gzip',
                     'User-Agent': 'PrometeoCatastro/1.0'})
        with self.opener.open(request, timeout=30) as response:
            body = response.read(16 * 1024 * 1024 + 1)
            headers = dict(response.headers)
        if len(body) > 16 * 1024 * 1024:
            raise StorageError('La parte vectorial supera el límite de lectura.')
        return body, headers


def _storage(cloud=None):
    if cloud is not None:
        return cloud
    try:
        return WorkerVectorStorage()
    except StorageError:
        return R2(timeout=30)


def _index(cloud=None):
    try:
        body, _ = (cloud or R2(timeout=20)).get_manifest(INDEX_KEY)
        value = json.loads(body)
        return value if isinstance(value, dict) else {'snapshots': []}
    except StorageError as error:
        if 'HTTP 404' in str(error):
            return {'schema': 'prometeo-vector-snapshots-v1', 'snapshots': []}
        raise


def inventory(cloud=None):
    if cloud is None and LOCAL_INDEX.is_file():
        try:
            local = json.loads(LOCAL_INDEX.read_text(encoding='utf8'))
            rows = [
                row for row in local.get('snapshots', [])
                if isinstance(row, dict) and row.get('ubigeo')
                and row.get('layer') in LAYERS
            ]
            if rows:
                return {'schema': local.get('schema'), 'snapshots': rows}
        except (OSError, ValueError, TypeError):
            pass
    saved = cache.get('catastro-vector-snapshot-index-v1')
    if saved is not None:
        return saved
    value = _index(cloud)
    rows = [
        row for row in value.get('snapshots', [])
        if isinstance(row, dict) and row.get('ubigeo') and row.get('layer') in LAYERS
    ]
    result = {'schema': value.get('schema'), 'snapshots': rows}
    cache.set('catastro-vector-snapshot-index-v1', result, 60)
    return result


def clear_cache():
    cache.delete('catastro-vector-snapshot-index-v1')


def capture_district(ubigeo, layers=LAYERS, progress=None, cloud=None):
    """Extract immutable district/layer snapshots from the validated adapter."""
    from cuadrantizacion import geollaqta
    if ubigeo not in geollaqta.DISTRICTS:
        raise ValueError('UBIGEO no disponible en el catálogo vectorial.')
    results = []
    for layer in layers:
        if layer not in LAYERS:
            raise ValueError('Capa vectorial no válida: ' + str(layer))
        config = geollaqta.LAYERS['ejes-vias' if layer == 'vias' else layer]
        field = config.get('district_field', 'ID_DIST')
        inventory_result = geollaqta._query(
            layer=config['id'], where=field + "='" + ubigeo + "'",
            returnIdsOnly='true')
        ids = sorted(set(inventory_result.get('objectIds') or []))
        features = []
        for start in range(0, len(ids), 500):
            batch = geollaqta._query(
                layer=config['id'],
                objectIds=','.join(map(str, ids[start:start + 500])),
                outFields=config['fields'], returnGeometry='true', outSR=4326)
            for row in batch.get('features') or []:
                attributes = geollaqta._properties(
                    row.get('attributes') or {}, config['fields'])
                if attributes.get(field) != ubigeo:
                    continue
                if layer == 'vias':
                    attributes['TIPO_VIA'] = ROAD_TYPES.get(
                        str(attributes.get('TIP_VIA')), 'Otro')
                try:
                    geometry = geollaqta._esri_geometry(
                        row.get('geometry') or {}, config['kind'])
                except (ValueError, TypeError, IndexError, KeyError):
                    continue
                features.append({
                    'type': 'Feature', 'id': attributes.get('OBJECTID'),
                    'properties': attributes, 'geometry': geometry,
                })
            if progress:
                progress(layer, min(start + 500, len(ids)), len(ids))
        collection = {
            'type': 'FeatureCollection',
            'name': config['name'],
            'ubigeo': ubigeo,
            'layer': layer,
            'source_layer': 'ejes-vias' if layer == 'vias' else layer,
            'source': 'GeoLlaqta · COFOPRI',
            'features': features,
        }
        results.append(save_snapshot(ubigeo, layer, collection, cloud))
    return results


def save_snapshot(ubigeo, layer, collection, cloud=None, captured_at=None):
    if layer not in LAYERS or len(ubigeo) != 6 or not ubigeo.isdigit():
        raise ValueError('Distrito o capa vectorial no válida.')
    if not isinstance(collection, dict) or not isinstance(collection.get('features'), list):
        raise ValueError('La colección vectorial no es válida.')
    storage = _storage(cloud)
    stamp = captured_at or datetime.now(timezone.utc).isoformat()
    chunks = []
    features = collection['features']
    for index, start in enumerate(range(0, len(features), 4000), start=1):
        part = {**collection, 'features': features[start:start + 4000],
                'part': index}
        raw = json.dumps(part, ensure_ascii=False, separators=(',', ':')).encode()
        body = gzip.compress(raw, compresslevel=6)
        key = PREFIX + ubigeo + '/' + layer + '.part-%04d.json.gz' % index
        storage.put_verified(key, body, 'application/gzip')
        chunks.append({
            'object_key': key,
            'sha256': hashlib.sha256(raw).hexdigest(),
            'bytes': len(raw),
            'features': len(part['features']),
        })
    if not chunks:
        empty = {**collection, 'features': []}
        raw = json.dumps(empty, ensure_ascii=False, separators=(',', ':')).encode()
        body = gzip.compress(raw, compresslevel=6)
        key = PREFIX + ubigeo + '/' + layer + '.part-0001.json.gz'
        storage.put_verified(key, body, 'application/gzip')
        chunks.append({
            'object_key': key,
            'sha256': hashlib.sha256(raw).hexdigest(),
            'bytes': len(raw),
            'features': 0,
        })
    row = {
        'ubigeo': ubigeo,
        'layer': layer,
        'chunks': chunks,
        'bytes': sum(item['bytes'] for item in chunks),
        'features': sum(item['features'] for item in chunks),
        'captured_at': stamp,
    }
    index = _index(storage)
    snapshots = [
        item for item in index.get('snapshots', [])
        if not (isinstance(item, dict) and item.get('ubigeo') == ubigeo
                and item.get('layer') == layer)
    ]
    snapshots.append(row)
    snapshots.sort(key=lambda item: (str(item.get('ubigeo')), str(item.get('layer'))))
    payload = json.dumps(
        {'schema': 'prometeo-vector-snapshots-v1', 'snapshots': snapshots},
        ensure_ascii=False, separators=(',', ':')).encode()
    storage.put_verified(INDEX_KEY, payload, 'application/json')
    clear_cache()
    return row


def read_snapshot(ubigeo, layer, cloud=None):
    if layer not in LAYERS or len(ubigeo) != 6 or not ubigeo.isdigit():
        raise ValueError('Distrito o capa vectorial no válida.')
    row = next((item for item in inventory(cloud)['snapshots']
                if item.get('ubigeo') == ubigeo and item.get('layer') == layer), None)
    if not row:
        raise ValueError('La capa vectorial todavía no está disponible.')
    storage = _storage(cloud)
    chunks = row.get('chunks') or ([{
        'object_key': row['object_key'],
        'sha256': row['sha256'],
    }] if row.get('object_key') else [])
    if not chunks:
        raise StorageError('La capa vectorial no tiene partes almacenadas.')
    result = None
    features = []
    for item in chunks:
        body, _ = storage.get_manifest(item['object_key'])
        raw = gzip.decompress(body)
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise StorageError('La capa vectorial no coincide con su huella registrada.')
        value = json.loads(raw)
        if not isinstance(value, dict) or not isinstance(value.get('features'), list):
            raise StorageError('La capa vectorial almacenada no es válida.')
        if result is None:
            result = value
        features.extend(value['features'])
    return {**result, 'features': features, 'total_features': len(features)}


def snapshot_manifest(ubigeo, layer, cloud=None):
    row = next((item for item in inventory(cloud)['snapshots']
                if item.get('ubigeo') == ubigeo and item.get('layer') == layer), None)
    if not row:
        raise ValueError('La capa vectorial todavía no está disponible.')
    chunks = row.get('chunks') or ([{
        'object_key': row['object_key'], 'sha256': row['sha256'],
        'features': row.get('features', 0),
    }] if row.get('object_key') else [])
    return {
        'ubigeo': ubigeo, 'layer': layer, 'parts': len(chunks),
        'features': row.get('features', 0),
        'chunks': [{'part': index + 1, 'features': item.get('features', 0),
                    'sha256': item['sha256']}
                   for index, item in enumerate(chunks)],
    }


def read_snapshot_part(ubigeo, layer, part, cloud=None):
    row = next((item for item in inventory(cloud)['snapshots']
                if item.get('ubigeo') == ubigeo and item.get('layer') == layer), None)
    if not row:
        raise ValueError('La capa vectorial todavía no está disponible.')
    chunks = row.get('chunks') or ([{
        'object_key': row['object_key'], 'sha256': row['sha256'],
    }] if row.get('object_key') else [])
    if type(part) is not int or not 1 <= part <= len(chunks):
        raise ValueError('Parte vectorial no válida.')
    item = chunks[part - 1]
    body, _ = _storage(cloud).get_manifest(item['object_key'])
    raw = gzip.decompress(body)
    if hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise StorageError('La parte vectorial no coincide con su huella registrada.')
    value = json.loads(raw)
    if not isinstance(value, dict) or not isinstance(value.get('features'), list):
        raise StorageError('La parte vectorial almacenada no es válida.')
    return value


def snapshot_fingerprint(ubigeo, layer, cloud=None):
    row = next((item for item in inventory(cloud)['snapshots']
                if item.get('ubigeo') == ubigeo and item.get('layer') == layer), None)
    if not row:
        return None
    return hashlib.sha256(
        json.dumps(row.get('chunks') or row, sort_keys=True,
                   separators=(',', ':')).encode()).hexdigest()


def catalog_sources(cloud=None):
    grouped = {}
    for row in inventory(cloud)['snapshots']:
        grouped.setdefault(row['ubigeo'], {})[row['layer']] = row
    return [{
        'id': 'vectores-' + ubigeo,
        'name': 'Catastro Maestro · vectores del distrito',
        'ubigeo': ubigeo,
        'districts': [ubigeo],
        'active': True,
        'default_visible': True,
        'contributes': False,
        'reference_only': False,
        'role': 'snapshot',
        'status': 'available_vectors',
        'transport': 'snapshot',
        'crs': 'EPSG:4326',
        'layers': {
            layer: {'count': int(item.get('features') or 0), 'kind': 'polygon'}
            for layer, item in layers.items()
        },
        'snapshot_schema': 'prometeo-vector-snapshots-v1',
    } for ubigeo, layers in sorted(grouped.items())]
