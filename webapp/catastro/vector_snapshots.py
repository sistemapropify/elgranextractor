"""Independent district/layer vector snapshots stored outside primary services."""
import gzip
import hashlib
import json
import re
import time
from http.cookiejar import CookieJar
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from django.core.cache import cache

from .storage import R2, StorageError

PREFIX = 'geollaqta/vectores/'
INDEX_KEY = PREFIX + 'index.json'
LAYERS = ('lotes', 'manzanas', 'vias')
LOCAL_INDEX = Path(__file__).with_name('data') / 'geollaqta-vector-index.json'
LOCAL_BOUNDS = Path(__file__).with_name('data') / 'geollaqta-vector-bounds.json'
ROAD_TYPES = {
    '1': 'Avenida', '2': 'Calle', '3': 'Jirón', '4': 'Pasaje',
    '7': 'Prolongación', '13': 'Callejón',
}
PORTAL = 'https://catastro.cofopri.gob.pe/geollaqta/'
FORMALIZATION_DETAIL_FIELDS = (
    'FI_CODPRE', 'NOMPJV', 'MZNA', 'LOTE', 'EDI_PISO', 'EDI_DPTO',
    'TIPO_USO', 'PM_AREPRE', 'FECHA_TITULO', 'ESTADO_TITULO',
    'FC_FRENTE', 'PM_LTEFRE', 'FC_DERECHA', 'PM_LTEDER',
    'FC_IZQUIERDA', 'PM_LTEIZQ', 'FC_FONDO', 'PM_LTEFON',
    'ULTIMA_ACTUALIZACION',
)
SOURCE_PROFILES = {
    'pcdpi': {
        'name': 'GeoLlaqta · Catastro PCDPI',
        'service_base': 'https://geoportal.cofopri.gob.pe/giscofopri/rest/services/Cofopri/Catastro_PCDPI/MapServer',
        'crs': 'EPSG:4326',
        'layers': {
            'lotes': {
                'id': 10, 'name': 'Lotes', 'kind': 'polygon',
                'district_field': 'ID_DIST',
                'fields': 'OBJECTID,ID_LOTE,ID_DIST,COD_LOTE,COD_MZNA,COD_SECT,AREA_TER,AREA_CON,NIVELES,ANIO_CAT,NRO_UNIDADES,CUC,ID_PLANO,AREA_GRAFICA',
            },
            'manzanas': {
                'id': 11, 'name': 'Manzanas', 'kind': 'polygon',
                'district_field': 'ID_DIST',
                'fields': 'OBJECTID,ID_DIST,COD_MZNA,COD_SECT,ID_MZNA,ANIO_CAT',
            },
            'vias': {
                'id': 0, 'name': 'Ejes de vías', 'kind': 'line',
                'district_field': 'ID_UBI_GEO',
                'fields': 'OBJECTID,ID_UBI_GEO,COD_VIA,TIP_VIA,NOM_VIA',
            },
        },
    },
    'wgs84': {
        'name': 'GeoLlaqta · Formalización WGS84',
        'service_base': 'https://geoportal.cofopri.gob.pe/giscofopri/rest/services/Cofopri/FORMALIZACION_WGS84/MapServer',
        'crs': 'EPSG:4326',
        'layers': {
            'lotes': {
                'id': 1, 'name': 'Predios formalizados WGS84', 'kind': 'polygon',
                'district_field': 'ID_DIST',
                'fields': 'OBJECTID,ID_PREDIO_RPU,ID_DIST,NRO_MZNA,NRO_LOTE',
            },
            'manzanas': {
                'id': 2, 'name': 'Manzanas formalizadas WGS84', 'kind': 'polygon',
                'district_field': 'ID_DIST',
                'fields': 'OBJECTID,ID_DIST,ID_MZNA,ID_PUEBLO,ID_PUEBLO_TIT,TIP_FUENTE,NRO_MZNA,AREA_GRAFICA,FECH_TRAN,ID_PLANO,SITUACION',
            },
            'vias': {
                'id': 0, 'name': 'Calles formalizadas WGS84', 'kind': 'line',
                'district_field': 'ID_DIST',
                'fields': 'OBJECTID,ID_DIST,ID_CALLE,ID_PLANO,ID_PUEBLO,ID_PUEBLO_TIT,NOM_CALLE,FECH_TRAN',
            },
        },
    },
    'psad56': {
        'name': 'GeoLlaqta · Formalización PSAD56',
        'service_base': 'https://geoportal.cofopri.gob.pe/giscofopri/rest/services/Cofopri/FORMALIZACION_PSAD56/MapServer',
        'crs': 'EPSG:4248',
        'layers': {
            'lotes': {
                'id': 1, 'name': 'Predios formalizados PSAD56', 'kind': 'polygon',
                'district_field': 'ID_DIST',
                'fields': 'OBJECTID,VAR_ARANCEL,AREA_INSCRITA,ID_LOTE,ID_MZNA,NRO_MZNA,NRO_LOTE,AREA_GRAFICA2,TIP_USO,DETALLE_USO,TIP_PREDIO,ID_DIST,ID_PLANO,ID_PUEBLO_TIT,ID_PREDIO_RPU,FECH_TRAN,CODI_USER,ID_PROV,ID_DPTO,ADJUDICATARIO,ID_PUEBLO,EDIFICACIONES,TIP_FUENTE,AREA_GRAFICA,FLAG_FORMALIZA,CUC',
            },
            'manzanas': {
                'id': 2, 'name': 'Manzanas formalizadas PSAD56', 'kind': 'polygon',
                'district_field': 'ID_DIST',
                'fields': 'OBJECTID,ID_DIST,ID_MZNA,ID_PUEBLO,ID_PUEBLO_TIT,TIP_FUENTE,NRO_MZNA,AREA_GRAFICA,FECH_TRAN,CODI_USER,ID_PLANO,SITUACION,ID_DPTO,ID_PROV',
            },
            'vias': {
                'id': 0, 'name': 'Calles formalizadas PSAD56', 'kind': 'line',
                'district_field': 'ID_DIST',
                'fields': 'OBJECTID,ID_DIST,ID_CALLE,ID_PLANO,ID_PUEBLO,ID_PUEBLO_TIT,NOM_CALLE,FECH_TRAN,CODI_USER',
            },
        },
    },
}
SOURCE_KEYS = tuple(SOURCE_PROFILES)
DEFAULT_SOURCE = 'pcdpi'


def _source_key(value):
    source = str(value or DEFAULT_SOURCE)
    if source not in SOURCE_PROFILES:
        raise ValueError('Fuente vectorial no válida.')
    return source


def _source_profile(value):
    source = _source_key(value)
    return SOURCE_PROFILES[source]


def _source_snapshot_prefix(ubigeo, source):
    if source == DEFAULT_SOURCE:
        return PREFIX + ubigeo + '/'
    return PREFIX + ubigeo + '/' + source + '/'


def source_id(ubigeo, source=DEFAULT_SOURCE):
    source = _source_key(source)
    return ('vectores-' + ubigeo if source == DEFAULT_SOURCE
            else 'vectores-' + source + '-' + ubigeo)


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
                {**row, 'source': row.get('source') or DEFAULT_SOURCE}
                for row in local.get('snapshots', [])
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
        {**row, 'source': row.get('source') or DEFAULT_SOURCE}
        for row in value.get('snapshots', [])
        if isinstance(row, dict) and row.get('ubigeo') and row.get('layer') in LAYERS
        and (row.get('source') or DEFAULT_SOURCE) in SOURCE_PROFILES
    ]
    result = {'schema': value.get('schema'), 'snapshots': rows}
    cache.set('catastro-vector-snapshot-index-v1', result, 60)
    return result


def clear_cache():
    cache.delete('catastro-vector-snapshot-index-v1')


def _query_profile(source, layer, **params):
    from cuadrantizacion.geollaqta import _download
    profile = _source_profile(source)
    config = profile['layers'][layer]
    url = profile['service_base'] + '/' + str(config['id']) + '/query'
    try:
        value = json.loads(_download(url, {'f': 'json', **params}))
    except (TypeError, ValueError, UnicodeError) as error:
        raise RuntimeError('COFOPRI devolvió una consulta vectorial no válida.') from error
    if not isinstance(value, dict) or value.get('error'):
        raise RuntimeError('COFOPRI no pudo completar la consulta vectorial.')
    return value


def _transform_geometry(geometry, source):
    """Geometry has already been reprojected by ArcGIS via outSR=4326."""
    _source_key(source)
    return geometry


def _normalized_properties(source, layer, attributes):
    values = dict(attributes)
    if source in ('wgs84', 'psad56'):
        if layer == 'lotes':
            values.setdefault('COD_MZNA', values.get('NRO_MZNA'))
            values.setdefault('COD_LOTE', values.get('NRO_LOTE'))
            values.setdefault('AREA_TER', values.get('AREA_INSCRITA'))
            values['MASTER_LAYER'] = 'lotes'
        elif layer == 'manzanas':
            values.setdefault('COD_MZNA', values.get('NRO_MZNA'))
            values['MASTER_LAYER'] = 'manzanas'
        else:
            values.setdefault('NOM_VIA', values.get('NOM_CALLE'))
            values.setdefault('COD_VIA', values.get('ID_CALLE'))
            values.setdefault('TIPO_VIA', 'Calle')
            values['MASTER_LAYER'] = 'vias'
        values['SOURCE_PROFILE'] = source
    return values


def formalization_details(predio, object_id):
    """Read an official formalization report without copying owner records."""
    predio = str(predio or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9-]{5,40}', predio):
        raise ValueError('Código de predio formalizado no válido.')
    if type(object_id) is not int or object_id <= 0:
        raise ValueError('Identificador del predio formalizado no válido.')
    from .storage import NoRedirect
    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar), NoRedirect())
    page_url = PORTAL + 'reporte/lote.php?' + urlencode({
        'cod_predio': predio, 'cod': object_id})
    request = Request(page_url, headers={
        'User-Agent': 'Prometeo-Catastro/1.0',
        'Accept': 'text/html,application/xhtml+xml',
    })
    with opener.open(request, timeout=25) as response:
        page = response.read(2_000_001)
    if len(page) > 2_000_000:
        raise RuntimeError('La ficha formalizada supera el límite de lectura.')
    api_url = 'https://catastro.cofopri.gob.pe/ws_cofopri/ws.php?' + urlencode({
        'cod_predio': predio, 'cod': object_id})
    request = Request(api_url, headers={
        'User-Agent': 'Prometeo-Catastro/1.0',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Referer': page_url,
        'X-Requested-With': 'XMLHttpRequest',
    })
    with opener.open(request, timeout=25) as response:
        payload = response.read(2_000_001)
    if len(payload) > 2_000_000:
        raise RuntimeError('Los datos formalizados superan el límite de lectura.')
    value = json.loads(payload)
    rows = value.get('predio') if isinstance(value, dict) else None
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise RuntimeError('COFOPRI no devolvió la ficha del predio formalizado.')
    row = rows[0]
    result = {
        'FORMALIZATION_DETAIL_SOURCE': 'COFOPRI · reporte/lote.php',
        'FORMALIZATION_DETAIL_STATUS': 'available',
    }
    for field in FORMALIZATION_DETAIL_FIELDS:
        if row.get(field) not in (None, ''):
            result[field] = row[field]
    result.update({
        'TITULO_FECHA': row.get('FECHA_TITULO'),
        'TITULO_ESTADO': row.get('ESTADO_TITULO'),
        'LINDERO_FRENTE': row.get('FC_FRENTE'),
        'MEDIDA_FRENTE': row.get('PM_LTEFRE'),
        'LINDERO_DERECHA': row.get('FC_DERECHA'),
        'MEDIDA_DERECHA': row.get('PM_LTEDER'),
        'LINDERO_IZQUIERDA': row.get('FC_IZQUIERDA'),
        'MEDIDA_IZQUIERDA': row.get('PM_LTEIZQ'),
        'LINDERO_FONDO': row.get('FC_FONDO'),
        'MEDIDA_FONDO': row.get('PM_LTEFON'),
    })
    return {key: value for key, value in result.items() if value not in (None, '')}


def formalization_detail(source, predio, object_id, ubigeo=''):
    """Return and cache one safe formalization detail payload."""
    source = _source_key(source)
    if source not in ('wgs84', 'psad56'):
        raise ValueError('La ficha formalizada no corresponde a esta fuente.')
    ubigeo = str(ubigeo or '').strip()
    if ubigeo and not re.fullmatch(r'\d{6}', ubigeo):
        raise ValueError('Distrito no válido para la ficha formalizada.')
    cache_key = 'cofopri-formalization-detail-v2:%s:%s:%s:%s' % (
        ubigeo, source, predio, object_id)
    saved = cache.get(cache_key)
    if saved is not None:
        return saved
    storage = None
    object_key = None
    if ubigeo:
        storage = R2(timeout=30)
        object_key = ('geollaqta/formalizacion/' + ubigeo + '/' +
                      source + '/' + predio + '.json')
        try:
            body, _ = storage.get_manifest(object_key)
            saved = json.loads(body)
            if (saved.get('ID_PREDIO_RPU') == predio
                    and saved.get('OBJECTID') == int(object_id)
                    and saved.get('source') == source):
                cache.set(cache_key, saved, 3600)
                return saved
        except StorageError as error:
            if error.http_status != 404:
                raise
    value = {
        'source': source,
        'source_name': _source_profile(source)['name'],
        'ID_PREDIO_RPU': str(predio),
        'OBJECTID': int(object_id),
        **formalization_details(predio, object_id),
    }
    if storage is not None:
        payload = json.dumps(
            value, ensure_ascii=False, separators=(',', ':')).encode()
        storage.put_verified(object_key, payload, 'application/json')
        value['PERSISTED_OBJECT_KEY'] = object_key
    cache.set(cache_key, value, 3600)
    return value


def capture_district(ubigeo, layers=LAYERS, progress=None, cloud=None,
                     source=DEFAULT_SOURCE, include_details=False,
                     detail_ids=None):
    """Extract immutable district/layer snapshots from the validated adapter."""
    from cuadrantizacion import geollaqta
    if ubigeo not in geollaqta.DISTRICTS:
        raise ValueError('UBIGEO no disponible en el catálogo vectorial.')
    source = _source_key(source)
    profile = _source_profile(source)
    selected_details = ({str(value).strip() for value in detail_ids}
                        if detail_ids else None)
    results = []
    for layer in layers:
        if layer not in LAYERS:
            raise ValueError('Capa vectorial no válida: ' + str(layer))
        config = profile['layers'][layer]
        field = config.get('district_field', 'ID_DIST')
        inventory_result = _query_profile(
            source, layer, where=field + "='" + ubigeo + "'",
            returnIdsOnly='true')
        ids = sorted(set(inventory_result.get('objectIds') or []))
        features = []
        for start in range(0, len(ids), 500):
            batch = _query_profile(
                source, layer,
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
                properties = _normalized_properties(source, layer, attributes)
                if (include_details and source in ('wgs84', 'psad56')
                        and layer == 'lotes'):
                    predio = str(properties.get('ID_PREDIO_RPU') or '').strip()
                    object_id = properties.get('OBJECTID')
                    if ((selected_details is None or predio in selected_details)
                            and predio and type(object_id) is int):
                        try:
                            properties.update(formalization_details(predio, object_id))
                        except (ValueError, RuntimeError, KeyError, TypeError) as error:
                            properties['FORMALIZATION_DETAIL_STATUS'] = 'unavailable'
                            properties['FORMALIZATION_DETAIL_ERROR'] = str(error)[:300]
                        time.sleep(.08)
                features.append({
                    'type': 'Feature', 'id': attributes.get('OBJECTID'),
                    'properties': properties,
                    'geometry': geometry,
                })
            if progress:
                progress(layer, min(start + 500, len(ids)), len(ids))
        collection = {
            'type': 'FeatureCollection',
            'name': config['name'],
            'ubigeo': ubigeo,
            'layer': layer,
            'source': profile['name'],
            'source_key': source,
            'source_crs': profile['crs'],
            'crs': 'EPSG:4326',
            'source_layer': ('ejes-vias' if layer == 'vias' and source == DEFAULT_SOURCE
                             else layer),
            'features': features,
        }
        results.append(save_snapshot(
            ubigeo, layer, collection, cloud, source=source))
    return results


def save_snapshot(ubigeo, layer, collection, cloud=None, captured_at=None,
                  source=DEFAULT_SOURCE):
    source = _source_key(source)
    if layer not in LAYERS or len(ubigeo) != 6 or not ubigeo.isdigit():
        raise ValueError('Distrito o capa vectorial no válida.')
    if not isinstance(collection, dict) or not isinstance(collection.get('features'), list):
        raise ValueError('La colección vectorial no es válida.')
    # WorkerVectorStorage is deliberately read-only. Captures always write
    # through the private R2 credential path, optionally supplied by tests.
    storage = cloud or R2(timeout=30)
    stamp = captured_at or datetime.now(timezone.utc).isoformat()
    prefix = _source_snapshot_prefix(ubigeo, source)
    chunks = []
    features = collection['features']
    for index, start in enumerate(range(0, len(features), 4000), start=1):
        part = {**collection, 'features': features[start:start + 4000],
                'part': index}
        raw = json.dumps(part, ensure_ascii=False, separators=(',', ':')).encode()
        body = gzip.compress(raw, compresslevel=6)
        key = prefix + layer + '.part-%04d.json.gz' % index
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
        key = prefix + layer + '.part-0001.json.gz'
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
        'source': source,
        'chunks': chunks,
        'bytes': sum(item['bytes'] for item in chunks),
        'features': sum(item['features'] for item in chunks),
        'captured_at': stamp,
    }
    index = _index(storage)
    snapshots = [
        item for item in index.get('snapshots', [])
        if not (isinstance(item, dict) and item.get('ubigeo') == ubigeo
                and item.get('layer') == layer
                and (item.get('source') or DEFAULT_SOURCE) == source)
    ]
    snapshots.append(row)
    snapshots.sort(key=lambda item: (
        str(item.get('ubigeo')), str(item.get('source') or DEFAULT_SOURCE),
        str(item.get('layer'))))
    payload = json.dumps(
        {'schema': 'prometeo-vector-snapshots-v1', 'snapshots': snapshots},
        ensure_ascii=False, separators=(',', ':')).encode()
    storage.put_verified(INDEX_KEY, payload, 'application/json')
    clear_cache()
    return row


def _find_snapshot(ubigeo, layer, source=DEFAULT_SOURCE, cloud=None):
    if layer not in LAYERS or len(ubigeo) != 6 or not ubigeo.isdigit():
        raise ValueError('Distrito o capa vectorial no válida.')
    source = _source_key(source)
    row = next((item for item in inventory(cloud)['snapshots']
                if item.get('ubigeo') == ubigeo and item.get('layer') == layer
                and (item.get('source') or DEFAULT_SOURCE) == source), None)
    if not row:
        raise ValueError('La capa vectorial todavía no está disponible.')
    return row


def read_snapshot(ubigeo, layer, cloud=None, source=DEFAULT_SOURCE):
    row = _find_snapshot(ubigeo, layer, source, cloud)
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


def snapshot_manifest(ubigeo, layer, cloud=None, source=DEFAULT_SOURCE):
    row = _find_snapshot(ubigeo, layer, source, cloud)
    chunks = row.get('chunks') or ([{
        'object_key': row['object_key'], 'sha256': row['sha256'],
        'features': row.get('features', 0),
    }] if row.get('object_key') else [])
    return {
        'ubigeo': ubigeo, 'layer': layer, 'source': row.get('source') or DEFAULT_SOURCE,
        'parts': len(chunks),
        'features': row.get('features', 0),
        'chunks': [{'part': index + 1, 'features': item.get('features', 0),
                    'sha256': item['sha256']}
                   for index, item in enumerate(chunks)],
    }


def read_snapshot_part(ubigeo, layer, part, cloud=None, source=DEFAULT_SOURCE):
    row = _find_snapshot(ubigeo, layer, source, cloud)
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


def snapshot_fingerprint(ubigeo, layer, cloud=None, source=DEFAULT_SOURCE):
    try:
        row = _find_snapshot(ubigeo, layer, source, cloud)
    except ValueError:
        return None
    if not row:
        return None
    return hashlib.sha256(
        json.dumps(row.get('chunks') or row, sort_keys=True,
                   separators=(',', ':')).encode()).hexdigest()


@lru_cache(maxsize=12)
def _cached_collection(ubigeo, layer, fingerprint, source=DEFAULT_SOURCE):
    return read_snapshot(ubigeo, layer, source=source)


def find_feature(ubigeo, layer, field, value, cloud=None, source=DEFAULT_SOURCE):
    """Find one archived vector without contacting a primary map service."""
    if layer not in LAYERS or not re.fullmatch(r'\d{6}', str(ubigeo or '')):
        raise ValueError('Distrito o capa vectorial no válida.')
    expected = str(value or '').strip()
    if not expected:
        raise ValueError('Código vectorial no válido.')
    source = _source_key(source)
    if cloud is None:
        fingerprint = snapshot_fingerprint(ubigeo, layer, source=source)
        collection = _cached_collection(
            ubigeo, layer, fingerprint or 'missing', source)
    else:
        collection = read_snapshot(
            ubigeo, layer, cloud=cloud, source=source)
    return next((feature for feature in collection.get('features', [])
                 if str((feature.get('properties') or {}).get(field) or '').strip()
                 == expected), None)


def catalog_sources(cloud=None):
    grouped = {}
    for row in inventory(cloud)['snapshots']:
        source = row.get('source') or DEFAULT_SOURCE
        grouped.setdefault((row['ubigeo'], source), {})[row['layer']] = row
    try:
        saved_bounds = json.loads(LOCAL_BOUNDS.read_text(encoding='utf8')).get('bounds') or {}
    except (OSError, TypeError, ValueError):
        saved_bounds = {}
    sources = []
    for (ubigeo, source), layers in sorted(grouped.items()):
        profile = _source_profile(source)
        revision = hashlib.sha256(json.dumps({
            layer: {'captured_at': item.get('captured_at'),
                    'source': source,
                    'chunks': item.get('chunks') or [
                        {'sha256': item.get('sha256')}]}
            for layer, item in layers.items()
        }, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        sources.append({
            'id': source_id(ubigeo, source),
            'name': 'Catastro Maestro · ' + profile['name'],
            'ubigeo': ubigeo,
            'districts': [ubigeo],
            'source_key': source,
            'source_name': profile['name'],
            'active': True,
            'default_visible': True,
            'contributes': False,
            'reference_only': False,
            'role': 'snapshot',
            'status': 'available_vectors',
            'transport': 'snapshot',
            'crs': 'EPSG:4326',
            'source_crs': profile['crs'],
            'bbox': saved_bounds.get(ubigeo),
            'revision': revision,
            'layers': {
                layer: {'count': int(item.get('features') or 0),
                        'kind': 'line' if layer == 'vias' else 'polygon'}
                for layer, item in layers.items()
            },
            'snapshot_schema': 'prometeo-vector-snapshots-v1',
        })
    return sources
