"""Administrative park-lot classifications owned by the Catastro Maestro."""
import hashlib
import json
import re
from datetime import datetime, timezone

from .storage import R2, StorageError


class Conflict(RuntimeError):
    pass


def _key(ubigeo):
    if not re.fullmatch(r'\d{6}', str(ubigeo or '')):
        raise ValueError('UBIGEO no válido.')
    return 'geollaqta/maestro/manual/parques/' + ubigeo + '.json'


def _validated(ubigeo, lots):
    if not isinstance(lots, list) or len(lots) > 250000:
        raise ValueError('La lista de parques no es válida.')
    values = sorted(set(str(value).strip() for value in lots))
    if any(not re.fullmatch(ubigeo + r'\d{8,12}', value) for value in values):
        raise ValueError('Todos los lotes deben pertenecer al distrito seleccionado.')
    return values


def read(ubigeo, cloud=None):
    key = _key(ubigeo)
    try:
        body, _ = (cloud or R2(timeout=20)).get_manifest(key)
        value = json.loads(body)
    except StorageError as error:
        if 'HTTP 404' in str(error):
            value = {}
        else:
            raise
    lots = _validated(ubigeo, value.get('lots', []))
    token = hashlib.sha256(
        json.dumps(lots, separators=(',', ':')).encode()).hexdigest()
    return {
        'ubigeo': ubigeo,
        'lots': lots,
        'token': token,
        'updated_at': value.get('updated_at'),
        'updated_by': value.get('updated_by'),
        'schema': 'prometeo-manual-parks-v1',
    }


def save(ubigeo, lots, expected_token, actor='administrador', cloud=None):
    current = read(ubigeo, cloud)
    if expected_token != current['token']:
        raise Conflict('La clasificación cambió. Vuelve a cargar antes de guardar.')
    values = _validated(ubigeo, lots)
    value = {
        'schema': 'prometeo-manual-parks-v1',
        'ubigeo': ubigeo,
        'lots': values,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'updated_by': str(actor or 'administrador')[:200],
    }
    body = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
    (cloud or R2(timeout=30)).put_verified(_key(ubigeo), body, 'application/json')
    return read(ubigeo, cloud)
