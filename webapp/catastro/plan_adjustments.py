"""Versioned visual adjustments; never rewrite DWG, source geometry or cadastre."""
import datetime
import json
import math
import os
import sqlite3
import uuid
from contextlib import closing, contextmanager
from . import cad_reader


class Conflict(ValueError):
    pass


@contextmanager
def _lock(path):
    # OS locks are released when a worker exits; a restart cannot strand a save.
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
            raise Conflict('Otro guardado está en curso. Vuelve a intentar.') from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def _path(job_id, crs):
    if crs not in cad_reader.CRS or crs == 'unknown':
        raise ValueError('Confirma el sistema de coordenadas antes de ajustar.')
    folder = cad_reader.directory(job_id)
    if cad_reader.status(job_id)['status'] != 'completed':
        raise ValueError('El plano todavía no está listo.')
    return folder / ('ajustes-' + crs.replace(':', '-') + '.json')


def read(job_id, crs):
    path = _path(job_id, crs)
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else dict(revision=0, groups=[])


def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _inside(point, ring):
    hit = False
    for i, b in enumerate(ring):
        a = ring[i-1]
        dx, dy = b[0]-a[0], b[1]-a[1]
        t = max(0, min(1, ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy or 1)))
        if math.hypot(point[0]-a[0]-t*dx, point[1]-a[1]-t*dy) < 1e-10:
            return True
        if (a[1] > point[1]) != (b[1] > point[1]) and point[0] < (b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0]:
            hit = not hit
    return hit


def _ring(geometry):
    if geometry['type'] != 'Polygon' or len(geometry['coordinates']) != 1:
        raise ValueError('La manzana requiere un único contorno cerrado.')
    ring = [p[:2] for p in geometry['coordinates'][0]]
    if ring[0] == ring[-1]:
        ring.pop()
    again = True
    while again and len(ring) > 3:
        again = False
        for i, b in enumerate(ring):
            a, c = ring[i-1], ring[(i+1) % len(ring)]
            if abs(cross(a, b, c)) <= 1e-10 * math.dist(a, b) * math.dist(b, c):
                ring.pop(i)
                again = True
                break
    return ring


def _validate(source, target):
    """Keep every original mesh triangle positive, so lots cannot fold over."""
    if not isinstance(target, list) or len(target) != len(source):
        raise ValueError('Las esquinas no coinciden con la manzana original.')
    if any(not isinstance(p, list) or len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) or abs(p[0]) > 180 or abs(p[1]) > 85 for p in target):
        raise ValueError('Coordenadas de ajuste no válidas.')
    sign = 1 if sum(cross(source[0], source[i], source[(i+1) % len(source)]) for i in range(len(source))) > 0 else -1
    ids = list(range(len(source)))
    mesh = []
    while len(ids) > 3:
        for k, b in enumerate(ids):
            a, c = ids[k-1], ids[(k+1) % len(ids)]
            if sign * cross(source[a], source[b], source[c]) <= 1e-18:
                continue
            def inside(i):
                return all(sign * value >= -1e-18 for value in (cross(source[a], source[b], source[i]), cross(source[b], source[c], source[i]), cross(source[c], source[a], source[i])))
            if any(inside(i) for i in ids if i not in (a, b, c)):
                continue
            mesh.append((a, b, c))
            ids.pop(k)
            break
        else:
            raise ValueError('El contorno original no permite ajustar sus esquinas.')
    mesh.append(ids)
    if any(sign * cross(target[a], target[b], target[c]) <= 1e-18 for a, b, c in mesh):
        raise ValueError('Ese ajuste invierte los lotes o cruza sus esquinas.')
    for i, a in enumerate(target):
        b = target[(i+1) % len(target)]
        for j in range(i+2, len(target)):
            if i == 0 and j == len(target)-1:
                continue
            c, d = target[j], target[(j+1) % len(target)]
            if cross(a,b,c)*cross(a,b,d) <= 0 and cross(c,d,a)*cross(c,d,b) <= 0 and max(min(a[0],b[0]),min(c[0],d[0])) <= min(max(a[0],b[0]),max(c[0],d[0])) and max(min(a[1],b[1]),min(c[1],d[1])) <= min(max(a[1],b[1]),max(c[1],d[1])):
                raise ValueError('El contorno ajustado se cruza.')


def save(job_id, crs, payload, author):
    path = _path(job_id, crs)
    groups = payload.get('groups')
    if type(payload.get('revision')) is not int or not isinstance(groups, list) or len(groups) > 3000:
        raise ValueError('Formato de ajustes no válido.')
    from pyproj import Transformer, network
    network.set_network_enabled(False)
    project = Transformer.from_crs(crs, 'EPSG:4326', always_xy=True, allow_ballpark=False)
    canonical, assigned, blocks = [], set(), set()
    database = cad_reader.directory(job_id) / 'geometries.sqlite3'
    with closing(sqlite3.connect('file:' + database.as_posix() + '?mode=ro', uri=True)) as db:
        for group in groups:
            if not isinstance(group, dict) or type(group.get('block_id')) is not int or group['block_id'] in blocks:
                raise ValueError('Manzana duplicada o no válida.')
            row = db.execute('SELECT layer,geometry FROM features WHERE id=?', (group['block_id'],)).fetchone()
            if not row or not any(word in row[0].lower() for word in ('manzan', 'mza')):
                raise ValueError('Selecciona el contorno de una manzana.')
            geometry = json.loads(row[1])
            def convert(v):
                return list(project.transform(*v[:2], errcheck=True)) if isinstance(v[0], (int, float)) else [convert(p) for p in v]
            geometry['coordinates'] = convert(geometry['coordinates'])
            source = _ring(geometry)
            if not 3 <= len(source) <= 512:
                raise ValueError('El contorno de la manzana es demasiado complejo.')
            supplied = group.get('source')
            if not isinstance(supplied, list) or len(supplied) != len(source) or any(not isinstance(p, list) or len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) or math.dist(p, q) > 1e-10 for p, q in zip(supplied, source)):
                raise ValueError('El original cambió; vuelve a cargar el plano.')
            _validate(source, group.get('target'))
            members = group.get('member_ids')
            if not isinstance(members, list) or not 1 <= len(members) <= 10000 or any(type(i) is not int for i in members) or len(set(members)) != len(members) or group['block_id'] not in members or assigned.intersection(members):
                raise ValueError('Los lotes no pueden pertenecer a dos ajustes distintos.')
            found = set()
            for start in range(0, len(members), 500):
                part = members[start:start+500]
                for member_id, member_layer, raw_geometry in db.execute('SELECT id,layer,geometry FROM features WHERE id IN (' + ','.join('?' for _ in part) + ')', part):
                    if member_id != group['block_id']:
                        child = json.loads(raw_geometry)
                        if not any(w in member_layer.lower() for w in ('lote', 'parcela', 'predio', 'manzan', 'mza')) or child['type'] != 'Point' and any(w in member_layer.lower() for w in ('manzan', 'mza')):
                            raise ValueError('El ajuste incluye entidades ajenas a la manzana.')
                        def inside_all(v):
                            return _inside(project.transform(*v[:2], errcheck=True), source) if isinstance(v[0], (int, float)) else all(inside_all(p) for p in v)
                        if not inside_all(child['coordinates']):
                            raise ValueError('Un lote cruza el contorno de otra manzana; revisa la selección.')
                    found.add(member_id)
            if found != set(members):
                raise ValueError('Una entidad del ajuste no pertenece a este plano.')
            canonical.append(dict(block_id=group['block_id'], source=source, target=group['target'], member_ids=members))
            blocks.add(group['block_id'])
            assigned.update(members)
    temporary = path.with_name(uuid.uuid4().hex + '.tmp')
    try:
        with _lock(path.with_suffix('.lock')):
            previous = read(job_id, crs)
            if previous['revision'] != payload['revision']:
                raise Conflict('Otra sesión guardó cambios. Recarga el plano antes de continuar; tus cambios siguen en pantalla.')
            result = dict(revision=previous['revision']+1, groups=canonical, updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), updated_by=str(author)[:160], source_crs=crs)
            if path.exists():
                history = path.parent / 'historial-ajustes'
                history.mkdir(exist_ok=True)
                (history / (crs.replace(':','-') + '-' + str(previous['revision']) + '.json')).write_bytes(path.read_bytes())
            temporary.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding='utf8')
            temporary.replace(path)
            return result
    finally:
        temporary.unlink(missing_ok=True)
