"""Versioned source and block registration. Original GeoJSON is immutable."""
import datetime
import json
import math
import os
from contextlib import contextmanager
from functools import lru_cache


class Conflict(ValueError):
    pass


@contextmanager
def _lock(path):
    with path.open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Conflict('Hay otro guardado en curso. Vuelve a intentar.') from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def read(folder):
    from . import shared_placement
    return shared_placement.read(folder) if shared_placement.enabled() else read_local(folder)


def read_local(folder):
    path = folder/'placement.json'
    value = json.loads(path.read_text(encoding='utf8')) if path.exists() else {
        'revision': 0, 'east_m': 0., 'north_m': 0., 'locked': True, 'history': []}
    return {'blocks': {}, **value}


@lru_cache(maxsize=8)
def _anchors(path, modified):
    features = json.loads(path.read_text(encoding='utf8'))['features']
    def points(value):
        if isinstance(value[0], (int, float)):
            yield value
        else:
            for item in value:
                yield from points(item)
    result = {}
    for feature in features:
        coords = list(points(feature['geometry']['coordinates']))
        result[feature['id']] = ((min(p[0] for p in coords)+max(p[0] for p in coords))/2,
                                 (min(p[1] for p in coords)+max(p[1] for p in coords))/2)
    return result


def anchors(folder):
    path = folder/'manzanas.geojson'
    return _anchors(path, path.stat().st_mtime_ns)


def validate_blocks(folder, blocks):
    known = anchors(folder)
    if not isinstance(blocks, dict) or len(blocks) > len(known):
        raise ValueError('Lista de ajustes de manzanas no válida.')
    for block_id, transform in blocks.items():
        if block_id not in known or not isinstance(transform, dict):
            raise ValueError('La manzana no pertenece a esta fuente.')
        for key in ('east_m', 'north_m', 'scale'):
            value = transform.get(key)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError('El ajuste de la manzana debe contener valores finitos.')
        if abs(transform['east_m']) > 2000 or abs(transform['north_m']) > 2000:
            raise ValueError('La manzana puede desplazarse hasta 2000 metros por eje.')
        if not .1 <= transform['scale'] <= 10:
            raise ValueError('El tamaño de la manzana debe estar entre 10 % y 1000 %.')
    return {key: {k: item[k] for k in ('east_m', 'north_m', 'scale')} for key, item in blocks.items()}


def degrees(placement, latitude):
    sy = 6371008.8*math.pi/180
    return placement['east_m']/(sy*math.cos(math.radians(latitude))), placement['north_m']/sy


def validate_payload(folder, payload):
    if not isinstance(payload, dict) or type(payload.get('revision')) is not int or payload.get('locked') is not True:
        raise ValueError('Confirma la revisión y usa Inmovilizar para guardar.')
    for key in ('east_m', 'north_m'):
        if type(payload.get(key)) not in (int, float) or not math.isfinite(payload[key]) or abs(payload[key]) > 2000:
            raise ValueError('El desplazamiento debe estar entre -2000 y 2000 metros.')
    if 'blocks' in payload:
        validate_blocks(folder, payload['blocks'])


def save(folder, payload, author):
    validate_payload(folder, payload)
    from . import shared_placement
    if shared_placement.enabled():
        return shared_placement.save(folder, payload, author)
    with _lock(folder/'placement.lock'):
        current = read(folder)
        if current['revision'] != payload['revision']:
            raise Conflict('La posición cambió en otra ventana. Recarga antes de ajustar.')
        value = {key: payload[key] for key in ('east_m', 'north_m', 'locked')}
        value['blocks'] = validate_blocks(folder, payload['blocks']) if 'blocks' in payload else current.get('blocks', {})
        value.update(revision=current['revision']+1, updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     updated_by=str(author))
        value['history'] = [*current.get('history', []), {k: v for k, v in current.items() if k != 'history'}][-100:]
        path = folder/'placement.json'
        pending = path.with_suffix('.json.tmp')
        pending.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        os.replace(pending, path)
        return value
