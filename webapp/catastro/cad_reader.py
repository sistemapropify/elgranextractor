"""Private DWG imports: native conversion, layer inventory and paged geometry.

Originals never execute code, load external references or change the master cadastre.
"""
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid

from .state import data_dir, ROOT

MAX_UPLOAD = 100 * 1024 * 1024
CRS = {'unknown': 'Sin definir · vista CAD', 'EPSG:32719': 'WGS84 / UTM 19S',
       'EPSG:24879': 'PSAD56 / UTM 19S', 'EPSG:32718': 'WGS84 / UTM 18S',
       'EPSG:24878': 'PSAD56 / UTM 18S', 'EPSG:4326': 'WGS84 · longitud / latitud'}


def imports_root():
    return data_dir() / 'planos'


def directory(job_id):
    if not re.fullmatch('[a-f0-9]{32}', str(job_id)):
        raise ValueError('Plano no encontrado.')
    return imports_root() / job_id


def write_status(folder, **changes):
    path = folder / 'estado.json'
    data = json.loads(path.read_text(encoding='utf8')) if path.is_file() else {}
    data.update(changes, updated=time.time())
    temporary = folder / ('estado-' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
        # Windows antivirus/indexers may briefly hold the destination open.
        # Keep the previous complete JSON available while retrying the rename.
        for attempt in range(8):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(min(.025 * 2**attempt, .4))
    finally:
        temporary.unlink(missing_ok=True)
    return data


def status(job_id):
    path = directory(job_id) / 'estado.json'
    if not path.is_file():
        raise ValueError('Plano no encontrado.')
    value = json.loads(path.read_text(encoding='utf8'))
    if value['status'] in ('queued', 'running') and value['updated'] < time.time() - 900:
        value = write_status(path.parent, status='failed', message='La lectura se interrumpió. El original sigue guardado; vuelve a cargarlo para reintentar.')
    return value


def converter_path():
    configured = os.environ.get('CATASTRO_DWG_CONVERTER')
    if configured:
        path = Path(configured)
        return path if path.is_absolute() and path.is_file() else None
    found = shutil.which('dwg2dxf')
    if found:
        return Path(found)
    bundled = ROOT / 'cad-runtime' / 'bin' / 'dwg2dxf'
    if os.name != 'nt' and bundled.is_file() and os.access(bundled, os.X_OK):
        return bundled
    local = Path.home() / '.codex/tools/libredwg/0.14/dwg2dxf.exe'
    return local if os.name == 'nt' and local.is_file() else None


def available():
    return bool(converter_path() and importlib.util.find_spec('ezdxf') and importlib.util.find_spec('pyproj'))


def start_import(upload):
    if not upload or Path(upload.name).suffix.lower() != '.dwg':
        raise ValueError('Selecciona un archivo DWG.')
    if upload.size > MAX_UPLOAD:
        raise ValueError('El DWG supera los 100 MB admitidos por esta instancia.')
    if not converter_path():
        raise RuntimeError('El lector DWG no está instalado en este servidor.')
    try:
        import ezdxf  # Check the actual runtime before accepting the upload.
        import pyproj
    except ImportError:
        raise RuntimeError('Faltan las bibliotecas de lectura CAD en este servidor.') from None
    root = imports_root()
    root.mkdir(parents=True, exist_ok=True)
    lock = root / 'conversion.lock'
    try:
        handle = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if lock.stat().st_mtime > time.time() - 900:
            raise ValueError('Ya hay un plano en lectura. Espera a que termine antes de cargar otro.') from None
        lock.unlink()
        handle = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    job_id = uuid.uuid4().hex
    with os.fdopen(handle, 'w') as stream:
        stream.write(job_id)
    folder = directory(job_id)
    folder.mkdir()
    try:
        digest = hashlib.sha256()
        size = 0
        original = folder / 'original.dwg'
        with original.open('wb') as stream:
            for chunk in upload.chunks():
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise ValueError('El DWG supera los 100 MB admitidos por esta instancia.')
                digest.update(chunk)
                stream.write(chunk)
        with original.open('rb') as stream:
            signature = stream.read(6)
        if signature not in (b'AC1009', b'AC1012', b'AC1014', b'AC1015', b'AC1018', b'AC1021', b'AC1024', b'AC1027', b'AC1032'):
            raise ValueError('El archivo no contiene una cabecera DWG compatible.')
        filename = str(upload.name).replace('\\', '/').split('/')[-1][:180]
        write_status(folder, id=job_id, filename=filename, bytes=size, sha256=digest.hexdigest(),
                     version=signature.decode('ascii'), status='queued', message='DWG recibido. Preparando lectura de capas.', layers=[])
        kwargs = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL, close_fds=True)
        if os.name == 'nt':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        else:
            kwargs['start_new_session'] = True
        process = subprocess.Popen([sys.executable, str(ROOT / 'scripts/read_cad.py'), '--job-id', job_id], **kwargs)
        return job_id
    except Exception:
        if lock.is_file() and lock.read_text() == job_id:
            lock.unlink()
        raise


def read_dxf(folder):
    import ezdxf
    from ezdxf.colors import aci2rgb
    from ezdxf.addons.geo import proxy
    from ezdxf.path import make_path
    document = ezdxf.readfile(folder / 'converted.dxf')
    connection = sqlite3.connect(folder / 'geometries.sqlite3')
    connection.execute('CREATE TABLE features (id INTEGER PRIMARY KEY, layer TEXT NOT NULL, geometry TEXT NOT NULL, properties TEXT NOT NULL)')
    connection.execute('CREATE INDEX features_layer ON features(layer,id)')
    inventory = {}
    skipped = {}
    bounds = [math.inf, math.inf, -math.inf, -math.inf]
    def color(entity, fallback='#71d5b2'):
        true_color = entity.dxf.get('true_color')
        if true_color is not None:
            return '#%06x' % true_color
        index = abs(entity.dxf.get('color', 256))
        if 1 <= index <= 255:
            return '#%02x%02x%02x' % aci2rgb(index)
        return fallback
    for layer in document.layers:
        inventory[layer.dxf.name] = dict(name=layer.dxf.name, count=0, drawable=0, color=color(layer), types={})
    processed = 0
    def entries(entities, inherited=None, depth=0, parent=''):
        for entity in entities:
            layer = str(entity.dxf.get('layer', '0'))
            if inherited and layer == '0':
                layer = inherited
            if entity.dxftype() == 'INSERT':
                if depth >= 8:
                    skipped['INSERT_PROFUNDO'] = skipped.get('INSERT_PROFUNDO', 0) + 1
                    continue
                try:
                    yield from entries(entity.virtual_entities(), layer, depth + 1, str(entity.dxf.get('handle', parent)))
                except (ValueError, ezdxf.DXFError):
                    skipped['INSERT'] = skipped.get('INSERT', 0) + 1
                continue
            yield entity, layer, parent
    try:
        for entity, layer, parent in entries(document.modelspace()):
            processed += 1
            if processed > 2000000:
                raise ValueError('El plano supera dos millones de entidades. Necesita procesamiento por sectores.')
            kind = entity.dxftype()
            row = inventory.setdefault(layer, dict(name=layer, count=0, drawable=0, color='#71d5b2', types={}))
            row['count'] += 1
            row['types'][kind] = row['types'].get(kind, 0) + 1
            properties = {'capa': layer, 'entidad_cad': kind, 'handle': str(entity.dxf.get('handle', '')),
                          'bloque_origen': parent, 'color': color(entity, row['color'])}
            geometry = None
            try:
                if kind in ('TEXT', 'MTEXT', 'POINT'):
                    point = entity.dxf.location if kind == 'POINT' else entity.dxf.insert
                    points = [[float(point.x), float(point.y)]]
                    geometry = dict(type='Point', coordinates=points[0])
                    if kind != 'POINT':
                        properties['texto'] = entity.plain_text()[:10000]
                elif kind in ('HATCH', 'MPOLYGON'):
                    geometry = proxy(entity, distance=.05).__geo_interface__
                    points = []
                    def xy(value):
                        if isinstance(value[0], (int, float)):
                            point = [float(value[0]), float(value[1])]
                            points.append(point)
                            if len(points) > 20000:
                                raise ValueError('polígono demasiado complejo')
                            return point
                        return [xy(item) for item in value]
                    geometry = dict(type=geometry['type'], coordinates=xy(geometry['coordinates']))
                elif kind in ('LINE', 'LWPOLYLINE', 'POLYLINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE', 'SOLID', 'TRACE', '3DFACE'):
                    path = make_path(entity)
                    vertices = list(itertools.islice(path.flattening(distance=.05, segments=8), 20001))
                    if len(vertices) > 20000:
                        raise ValueError('curva demasiado compleja')
                    points = [[float(point.x), float(point.y)] for point in vertices]
                    if len(points) >= 3 and path.is_closed:
                        if points[0] != points[-1]:
                            points.append(points[0])
                        geometry = dict(type='Polygon', coordinates=[points])
                    elif len(points) >= 2:
                        geometry = dict(type='LineString', coordinates=points)
                if geometry is None or not all(math.isfinite(v) and abs(v) < 1e12 for point in points for v in point):
                    raise ValueError('entidad no dibujable')
                for x, y in points:
                    bounds[:] = [min(bounds[0], x), min(bounds[1], y), max(bounds[2], x), max(bounds[3], y)]
                connection.execute('INSERT INTO features(layer,geometry,properties) VALUES (?,?,?)',
                                   (layer, json.dumps(geometry), json.dumps(properties, ensure_ascii=False)))
                row['drawable'] += 1
            except (ValueError, TypeError, AttributeError, NotImplementedError, ezdxf.DXFError):
                skipped[kind] = skipped.get(kind, 0) + 1
            if processed % 1000 == 0:
                connection.commit()
                write_status(folder, message=f'Leyendo entidades CAD: {processed:,}.')
        connection.commit()
    finally:
        connection.close()
    return dict(layers=sorted(inventory.values(), key=lambda row: row['name'].casefold()),
                entities=processed, drawable=sum(row['drawable'] for row in inventory.values()),
                unsupported=skipped, bounds=bounds if all(math.isfinite(v) for v in bounds) else None,
                units=int(document.units), cad_version=document.dxfversion)


def run_import(job_id):
    folder = directory(job_id)
    try:
        write_status(folder, status='running', message='Leyendo el DWG y convirtiendo sus entidades CAD.')
        converter = converter_path()
        if not converter:
            raise ValueError('El conversor DWG no está disponible.')
        with (folder / 'conversion.log').open('wb') as log:
            kwargs = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
            result = subprocess.run([str(converter), '-v0', '-o', str(folder / 'converted.dxf'), str(folder / 'original.dwg')],
                                    cwd=folder, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                    timeout=180, check=False, **kwargs)
        if result.returncode or not (folder / 'converted.dxf').is_file():
            raise ValueError('El conversor no pudo leer este DWG. El original se conserva para revisión.')
        write_status(folder, message='DWG leído. Inventariando capas, entidades y atributos.')
        data = read_dxf(folder)
        write_status(folder, status='completed', message='DWG leído. Selecciona las capas que quieres inspeccionar.', **data)
    except subprocess.TimeoutExpired:
        write_status(folder, status='failed', message='La conversión superó tres minutos. El original se conserva para revisión.')
    except Exception as error:
        message = str(error) if isinstance(error, ValueError) else 'No se pudo completar la lectura del plano. El original se conserva.'
        write_status(folder, status='failed', message=message[:350])
    finally:
        lock = imports_root() / 'conversion.lock'
        if lock.is_file() and lock.read_text() == job_id:
            lock.unlink()


def features(job_id, layer, offset=0, crs='unknown'):
    metadata = status(job_id)
    if metadata['status'] != 'completed':
        raise ValueError('El plano todavía no está listo.')
    if crs not in CRS or layer not in {row['name'] for row in metadata['layers']}:
        raise ValueError('Capa o sistema de coordenadas no válido.')
    if offset < 0 or offset > 2000000:
        raise ValueError('Página no válida.')
    transform = None
    if crs != 'unknown':
        from pyproj import Transformer, network
        network.set_network_enabled(False)
        transform = Transformer.from_crs(crs, 'EPSG:4326', always_xy=True, allow_ballpark=False)
    def coordinates(value):
        if isinstance(value[0], (float, int)):
            x, y = transform.transform(value[0], value[1], errcheck=True)
            if not math.isfinite(x) or not math.isfinite(y) or abs(x) > 180 or abs(y) > 90:
                raise ValueError('Estas coordenadas no se pueden ubicar con el sistema seleccionado.')
            return [x, y]
        return [coordinates(item) for item in value]
    connection = sqlite3.connect('file:' + (directory(job_id) / 'geometries.sqlite3').as_posix() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute('SELECT * FROM features WHERE layer=? ORDER BY id LIMIT 2001 OFFSET ?', (layer, offset))
        output = []
        vertices = 0
        more = False
        def count(value):
            return 1 if isinstance(value[0], (float, int)) else sum(count(item) for item in value)
        for row in rows:
            if len(output) >= 2000:
                more = True
                break
            geometry = json.loads(row['geometry'])
            size = count(geometry['coordinates'])
            if output and vertices + size > 60000:
                more = True
                break
            vertices += size
            if transform:
                geometry['coordinates'] = coordinates(geometry['coordinates'])
            properties = json.loads(row['properties'])
            properties.update(plano_origen=job_id, archivo_origen=metadata.get('filename', ''))
            output.append(dict(type='Feature', id=row['id'], geometry=geometry, properties=properties))
        return dict(type='FeatureCollection', features=output, next_offset=offset + len(output) if more else None,
                    source_crs=crs, georeferenced=crs != 'unknown')
    finally:
        connection.close()
