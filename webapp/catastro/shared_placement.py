"""One authoritative registration per approved source, with atomic R2 writes."""
import datetime
import hashlib
import json
import os
import re

from .storage import R2, StorageError, PreconditionFailed


def enabled():
    return os.environ.get('CATASTRO_SHARED_PLACEMENTS', '1' if os.environ.get('WEBSITE_SITE_NAME') else '0') == '1'


def key(folder):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}', folder.name):
        raise ValueError('Fuente compartida no válida.')
    return 'geollaqta/_master/'+folder.name+'/placement.json'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()


def _get(folder, cloud):
    body, headers = cloud.get(key(folder))
    try:
        value = json.loads(body)
        etag = next(v for k, v in headers.items() if k.lower() == 'etag')
        if not isinstance(value, dict) or type(value.get('revision')) is not int or value['revision'] < 0 or value.get('locked') is not True:
            raise ValueError()
        from .source_placement import validate_payload
        validate_payload(folder, {**value, 'blocks': value.get('blocks', {})})
        return value, etag
    except (ValueError, TypeError, KeyError, StopIteration):
        raise StorageError('El ajuste compartido requiere revisión; no se mostrará una posición anterior.') from None


def read(folder):
    try:
        return _get(folder, R2(timeout=5))[0]
    except StorageError as error:
        if error.http_status == 404:
            raise StorageError('El plano todavía no tiene un ajuste compartido inicializado.') from None
        raise


def _archive(folder, value, cloud):
    body = encoded(value)
    archive = key(folder).rsplit('/', 1)[0]+'/revisions/'+str(value['revision'])+'-'+hashlib.sha256(body).hexdigest()+'.json'
    cloud.put_verified(archive, body, 'application/json')
    return {'revision': value['revision'], 'object_key': archive}


def save(folder, payload, author):
    from .source_placement import Conflict, validate_payload
    validate_payload(folder, payload)
    cloud = R2(timeout=10)
    current, etag = _get(folder, cloud)
    if current['revision'] != payload['revision']:
        raise Conflict('Otra sesión guardó el plano. Recarga antes de continuar; tus cambios siguen en pantalla.')
    archive = _archive(folder, current, cloud)
    value = {k: payload[k] for k in ('east_m', 'north_m', 'locked')}
    value.update(blocks=payload.get('blocks', current.get('blocks', {})), revision=current['revision']+1,
                 updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), updated_by=str(author)[:160],
                 history=[*current.get('history', []), archive][-100:])
    body = encoded(value)
    try:
        cloud.put_conditional(key(folder), body, etag)
    except PreconditionFailed:
        raise Conflict('Otra sesión guardó el plano al mismo tiempo. Recarga antes de continuar.') from None
    except StorageError:
        # A lost PUT acknowledgement is resolved by reading the exact committed value.
        try:
            actual, _ = _get(folder, cloud)
            if encoded(actual) == body:
                return actual
        except StorageError:
            pass
        raise
    return value


def initialize(folder):
    """Import the latest local save once; never overwrite an existing cloud revision."""
    from .source_placement import _lock, read_local, validate_payload, Conflict
    with _lock(folder/'placement.lock'):
        cloud = R2(timeout=15)
        try:
            actual, _ = _get(folder, cloud)
        except StorageError as error:
            if error.http_status != 404:
                raise
        else:
            local = read_local(folder)
            if any(actual.get(k) != local.get(k) for k in ('revision', 'east_m', 'north_m', 'blocks')):
                raise Conflict('Ya hay un ajuste compartido distinto. No se reemplazará automáticamente.')
            return actual
        value = read_local(folder)
        validate_payload(folder, value)
        archive = _archive(folder, value, cloud)  # Includes the complete legacy history.
        current = {k: v for k, v in value.items() if k != 'history'}
        current['history'] = [archive]
        try:
            cloud.put_conditional(key(folder), encoded(current))
        except PreconditionFailed:
            raise Conflict('Otra sesión inicializó el plano. Revisa la versión compartida.') from None
        actual, _ = _get(folder, cloud)
        if encoded(actual) != encoded(current):
            raise StorageError('No se pudo verificar la importación del ajuste compartido.')
        return actual
