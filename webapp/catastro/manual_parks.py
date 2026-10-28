"""Manual lot classifications owned and published by the Catastro Maestro."""
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .storage import R2, StorageError


SCHEMA = 'prometeo-manual-lot-classifications-v2'
CATEGORIES = ('parks', 'corners', 'faces_park')
DEFAULT_COLORS = {
    'parks': '#54d48a',
    'corners': '#ff8c42',
    'faces_park': '#4f8cff',
}
CONFIG_KEY = 'geollaqta/maestro/manual/clasificaciones/config.json'


class Conflict(RuntimeError):
    pass


def _key(ubigeo):
    if not re.fullmatch(r'\d{6}', str(ubigeo or '')):
        raise ValueError('UBIGEO no válido.')
    return 'geollaqta/maestro/manual/clasificaciones/' + ubigeo + '.json'


def _legacy_key(ubigeo):
    return 'geollaqta/maestro/manual/parques/' + ubigeo + '.json'


def _validated(ubigeo, lots):
    if not isinstance(lots, list) or len(lots) > 250000:
        raise ValueError('La lista de lotes no es válida.')
    values = sorted(set(str(value).strip() for value in lots))
    if any(not re.fullmatch(ubigeo + r'\d{8,12}', value) for value in values):
        raise ValueError('Todos los lotes deben pertenecer al distrito seleccionado.')
    return values


def _color(value, fallback):
    candidate = str(value or '').strip()
    return candidate if re.fullmatch(r'#[0-9a-fA-F]{6}', candidate) else fallback


def _token(value):
    stable = {
        'parks': value['parks'],
        'corners': value['corners'],
        'faces_park': value['faces_park'],
        'colors': value['colors'],
    }
    return hashlib.sha256(
        json.dumps(stable, separators=(',', ':'), sort_keys=True).encode()
    ).hexdigest()


def _normalized(ubigeo, value, global_colors=None):
    lists = {
        'parks': _validated(ubigeo, value.get('parks', value.get('lots', []))),
        'corners': _validated(ubigeo, value.get('corners', [])),
        'faces_park': _validated(ubigeo, value.get('faces_park', [])),
    }
    saved_colors = value.get('colors') if isinstance(value.get('colors'), dict) else {}
    colors = {key: _color(saved_colors.get(key), DEFAULT_COLORS[key])
              for key in CATEGORIES}
    if global_colors:
        colors.update({key: _color(global_colors.get(key), colors[key])
                       for key in CATEGORIES})
    result = {
        'schema': SCHEMA,
        'ubigeo': ubigeo,
        **lists,
        'lots': lists['parks'],
        'colors': colors,
        'updated_at': value.get('updated_at'),
        'updated_by': value.get('updated_by'),
    }
    result['token'] = _token(result)
    return result


def _read_key(cloud, key):
    try:
        body, _ = cloud.get_manifest(key)
        return json.loads(body)
    except StorageError as error:
        if 'HTTP 404' in str(error):
            return None
        raise


def read_global_colors(cloud=None):
    cloud = cloud or R2(timeout=20)
    value = _read_key(cloud, CONFIG_KEY) or {}
    return {key: _color(value.get(key), DEFAULT_COLORS[key])
            for key in CATEGORIES}


def save_global_colors(colors, actor='administrador', cloud=None):
    cloud = cloud or R2(timeout=30)
    normalized = {key: _color((colors or {}).get(key), DEFAULT_COLORS[key])
                  for key in CATEGORIES}
    body = json.dumps({
        **normalized,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'updated_by': str(actor or 'administrador')[:200],
    }, ensure_ascii=False, separators=(',', ':')).encode()
    cloud.put_verified(CONFIG_KEY, body, 'application/json')
    return {'ubigeo': 'all', 'scope': 'all', 'colors': normalized}


def _stored(ubigeo, cloud):
    value = _read_key(cloud, _key(ubigeo))
    if value is None:
        value = _read_key(cloud, _legacy_key(ubigeo)) or {}
    return value


def read(ubigeo, cloud=None):
    cloud = cloud or R2(timeout=20)
    value = _stored(ubigeo, cloud)
    return _normalized(ubigeo, value, read_global_colors(cloud))


def read_all(ubigeos=None, cloud=None):
    cloud = cloud or R2(timeout=20)
    if ubigeos is None:
        from .master_layers import catalogue
        ubigeos = sorted({
            source['ubigeo'] for source in catalogue()['sources']
            if source.get('active')
            and source.get('role') in ('draft', 'snapshot')
            and source.get('ubigeo')
        })
    ubigeos = sorted({str(value) for value in ubigeos
                      if re.fullmatch(r'\d{6}', str(value))})
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(ubigeos)))) as pool:
        values = list(pool.map(
            lambda ubigeo: _normalized(ubigeo, _stored(ubigeo, cloud)),
            ubigeos))
    colors = read_global_colors(cloud)
    result = {
        'schema': SCHEMA,
        'ubigeo': 'all',
        'scope': 'all',
        'districts': ubigeos,
        'colors': colors,
    }
    for kind in CATEGORIES:
        result[kind] = sorted({
            lot for value in values for lot in value[kind]
        })
    result['lots'] = result['parks']
    result['token'] = _token(result)
    return result


def save_classifications(ubigeo, value, expected_token,
                         actor='administrador', cloud=None):
    cloud = cloud or R2(timeout=30)
    current = read(ubigeo, cloud)
    if expected_token != current['token']:
        raise Conflict('La clasificación cambió. Vuelve a cargar antes de guardar.')
    normalized = _normalized(ubigeo, value)
    save_global_colors(normalized['colors'], actor, cloud)
    saved = {
        'schema': SCHEMA,
        'ubigeo': ubigeo,
        'parks': normalized['parks'],
        'corners': normalized['corners'],
        'faces_park': normalized['faces_park'],
        'colors': normalized['colors'],
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'updated_by': str(actor or 'administrador')[:200],
    }
    body = json.dumps(saved, ensure_ascii=False,
                      separators=(',', ':')).encode()
    cloud.put_verified(_key(ubigeo), body, 'application/json')
    return read(ubigeo, cloud)


def save(ubigeo, lots, expected_token, actor='administrador', cloud=None):
    """Compatibility entry point for callers that only edit park lots."""
    current = read(ubigeo, cloud)
    return save_classifications(
        ubigeo,
        {
            'parks': lots,
            'corners': current['corners'],
            'faces_park': current['faces_park'],
            'colors': current['colors'],
        },
        expected_token if expected_token is not None else current['token'],
        actor,
        cloud,
    )
