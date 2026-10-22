"""Calibratable drone raster layers stored as Catastro Maestro versions."""
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
import math
import re

from PIL import ExifTags, Image

from . import master_contract
from .master_store import encoded, identifier
from .storage import R2, StorageError

OVERLAY_KIND = 'drone_orthophoto'
SOURCE_PREFIX = 'drone-raster-'
OBJECT_PATTERN = re.compile(
    r'geollaqta/maestro/raster/[a-f0-9]{64}\.(?:jpg|jpeg|png)')
_memory_images = {}


def _sha256(value):
    return hashlib.sha256(value).hexdigest()


def _gps_decimal(values, reference):
    if not isinstance(values, (tuple, list)) or len(values) != 3:
        return None
    try:
        degree, minutes, seconds = (float(item) for item in values)
    except (TypeError, ValueError):
        return None
    value = degree + minutes / 60 + seconds / 3600
    return -value if str(reference).upper() in ('S', 'W') else value


def _xmp_number(xmp, name):
    match = re.search(r'drone-dji:' + re.escape(name) + r'="([+-]?[0-9.]+)"', xmp or '')
    return float(match.group(1)) if match else None


def _metadata(body, filename):
    try:
        image = Image.open(BytesIO(body))
        image.verify()
        image = Image.open(BytesIO(body))
    except Exception as exc:
        raise ValueError('El archivo no es una imagen JPEG o PNG válida.') from exc
    if image.format not in ('JPEG', 'MPO', 'PNG'):
        raise ValueError('La capa satelital debe ser JPEG o PNG.')
    width, height = image.size
    if not (0 < width <= 12000 and 0 < height <= 12000 and width * height <= 50_000_000):
        raise ValueError('La imagen supera el tamaño seguro para una capa de mapa.')
    exif = image.getexif()
    gps = exif.get_ifd(34853) if exif.get(34853) else {}
    xmp = image.info.get('xmp', '')
    if isinstance(xmp, bytes):
        xmp = xmp.decode('utf8', errors='replace')
    latitude = _gps_decimal(gps.get(2), gps.get(1))
    longitude = _gps_decimal(gps.get(4), gps.get(3))
    if latitude is None or longitude is None:
        match = re.search(r'(-1[0-9]\.\d{4,})\s+(-7[0-9]\.\d{4,})', filename)
        if match:
            latitude, longitude = float(match.group(1)), float(match.group(2))
    if latitude is None or longitude is None or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError('La foto no contiene GPS utilizable. Indica el centro antes de cargarla.')
    captured_at = exif.get(36867) or exif.get(306)
    if isinstance(captured_at, str):
        captured_at = captured_at.replace(':', '-', 2).replace(' ', 'T')
    altitude = _xmp_number(xmp, 'RelativeAltitude')
    yaw = _xmp_number(xmp, 'GimbalYawDegree')
    # DJI Mini 4 Pro at 24 mm equivalent: approximately 73.7 degrees horizontal.
    width_m = round(2 * max(10.0, altitude or 100.0) * math.tan(math.radians(73.7 / 2)), 2)
    height_m = round(width_m * height / width, 2)
    return {
        'format': 'PNG' if image.format == 'PNG' else 'JPEG',
        'center': {'lat': round(latitude, 9), 'lng': round(longitude, 9)},
        'captured_at': captured_at,
        'camera': ' '.join(item for item in (exif.get(271), exif.get(272)) if item),
        'product': 'DJI Mini 4 Pro' if 'Mini4 Pro' in xmp else None,
        'relative_altitude_m': altitude,
        'gimbal_yaw_deg': yaw,
        'gimbal_pitch_deg': _xmp_number(xmp, 'GimbalPitchDegree'),
        'image_width': width,
        'image_height': height,
        'initial_width_m': width_m,
        'initial_height_m': height_m,
        'initial_rotation_deg': yaw or 0.0,
        'source_filename': filename[:300],
    }


def footprint(center, width_m, height_m, rotation_deg):
    """Rectangular WGS84 footprint for a rotated, north-up raster."""
    lat, lng = center['lat'], center['lng']
    angle = math.radians(rotation_deg)
    right = (math.cos(angle), -math.sin(angle))
    up = (math.sin(angle), math.cos(angle))
    metres_per_lat = 111320.0
    metres_per_lng = metres_per_lat * math.cos(math.radians(lat))
    if metres_per_lng <= 1:
        raise ValueError('La latitud no permite construir la huella de la imagen.')
    corners = []
    for across, along in ((-1, 1), (1, 1), (1, -1), (-1, -1), (-1, 1)):
        east = right[0] * width_m / 2 * across + up[0] * height_m / 2 * along
        north = right[1] * width_m / 2 * across + up[1] * height_m / 2 * along
        corners.append([round(lng + east / metres_per_lng, 9),
                        round(lat + north / metres_per_lat, 9)])
    return {'type': 'Polygon', 'coordinates': [corners]}


def _state(value, fallback=None):
    fallback = fallback or {}
    if not isinstance(value, dict):
        raise ValueError('La calibración de la capa no es válida.')
    center = value.get('center', fallback.get('center'))
    if not isinstance(center, dict):
        raise ValueError('Indica el centro de la imagen.')
    lat, lng = center.get('lat'), center.get('lng')
    if type(lat) not in (int, float) or type(lng) not in (int, float):
        raise ValueError('Las coordenadas del centro no son válidas.')
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError('El centro debe estar en WGS84.')
    width_m = value.get('width_m', fallback.get('width_m'))
    height_m = value.get('height_m', fallback.get('height_m'))
    rotation = value.get('rotation_deg', fallback.get('rotation_deg', 0))
    opacity = value.get('opacity', fallback.get('opacity', .75))
    for number, label, low, high in (
            (width_m, 'ancho', 5, 10000), (height_m, 'alto', 5, 10000),
            (rotation, 'rotación', -3600, 3600), (opacity, 'opacidad', 0, 1)):
        if type(number) not in (int, float) or not math.isfinite(number) or not low <= number <= high:
            raise ValueError('El valor de ' + label + ' no es válido.')
    return {
        'center': {'lat': round(float(lat), 10), 'lng': round(float(lng), 10)},
        'width_m': round(float(width_m), 3),
        'height_m': round(float(height_m), 3),
        'rotation_deg': round(float(rotation) % 360, 4),
        'opacity': round(float(opacity), 4),
        'visible': bool(value.get('visible', fallback.get('visible', True))),
        'locked': bool(value.get('locked', fallback.get('locked', True))),
    }


def _payload(overlay_id, name, ubigeo, metadata, state, original, label, nonce=None):
    raster = {
        'overlay_id': overlay_id,
        'state': state,
        'metadata': metadata,
        'footprint': footprint(state['center'], state['width_m'],
                               state['height_m'], state['rotation_deg']),
    }
    digest = _sha256(encoded([overlay_id, original['sha256'], state, nonce]).encode())
    version_id = overlay_id + ':v-' + digest[:24]
    return {
        'schema': 'catastro-maestro-raster-v1',
        'source': {'id': overlay_id, 'name': name, 'ubigeo': ubigeo, 'role': 'candidate'},
        'version': {
            'id': version_id,
            'label': label + ' ' + digest[:10],
            'source_date': (metadata.get('captured_at') or '')[:10] or None,
            'crs': 'EPSG:4326',
            'georeferencing': {
                'status': 'pending',
                'method': 'Huella rectangular ajustable; requiere revisión visual.',
                'evidence': {'raster_overlay_id': overlay_id, 'image_sha256': original['sha256']},
            },
            'original': original,
            'raster': raster,
        },
        'features': [],
        'environment_features': [{
            'id': overlay_id,
            'kind': OVERLAY_KIND,
            'name': name,
            'geometry': raster['footprint'],
            'evidence': {'raster': raster, 'status': 'candidate'},
        }],
    }


def _values(rows, published_only=False):
    values = {}
    for row in rows:
        payload = json.loads(row['payload'])
        raster = payload.get('version', {}).get('raster')
        if not raster or row['source_id'] in values:
            continue
        if published_only and (raster['state'].get('locked') is not True
                               or raster['state'].get('visible') is False):
            continue
        values[row['source_id']] = {
            'id': row['source_id'],
            'name': row['name'],
            'ubigeo': row['ubigeo'],
            'version_id': row['version_id'],
            'created_at': row['created_at'],
            'kind': OVERLAY_KIND,
            'state': raster['state'],
            'metadata': raster['metadata'],
            'footprint': raster['footprint'],
            'original': payload['version']['original'],
            'image_url': ('/catastro/api/maestro/raster/' + row['source_id'] +
                          '/imagen/?ubigeo=' + row['ubigeo']),
        }
    return list(values.values())


def _latest(store, ubigeo):
    if hasattr(store, 'scope'):
        store.summary(ubigeo)
    with store.lock:
        rows = store.db.execute(
            '''SELECT s.id AS source_id,s.name,s.ubigeo,v.id AS version_id,
                      v.created_at,v.payload
               FROM sources s JOIN versions v ON v.source_id=s.id
               WHERE s.ubigeo=? AND s.id LIKE ? ORDER BY v.created_at DESC''',
            (ubigeo, SOURCE_PREFIX + '%')).fetchall()
    return _values(rows)


def list_overlays(store, ubigeo):
    master_contract.validate_field('ubigeo', ubigeo)
    return _latest(store, ubigeo)


def list_all_overlays(store):
    """Return the latest validated patch per source for every map consumer."""
    query = '''SELECT s.id AS source_id,s.name,s.ubigeo,v.id AS version_id,
                      v.created_at,v.payload
               FROM sources s JOIN versions v ON v.source_id=s.id
               WHERE s.id LIKE ? ORDER BY v.created_at DESC'''
    if hasattr(store, 'gateway'):
        rows = store.gateway.read(query, [SOURCE_PREFIX + '%'])
    else:
        with store.lock:
            rows = [dict(row) for row in store.db.execute(query, (SOURCE_PREFIX + '%',))]
    return _values(rows, published_only=True)
def register_image(store, body, filename, name, ubigeo, actor='sistema', cloud=None):
    master_contract.validate_field('ubigeo', ubigeo)
    if not isinstance(body, bytes) or not 0 < len(body) <= 12 * 1024 * 1024:
        raise ValueError('La imagen debe medir hasta 12 MB.')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        raise ValueError('Escribe un nombre de capa de hasta 200 caracteres.')
    filename = str(filename or 'foto-dron.jpg')[:300]
    metadata = _metadata(body, filename)
    sha256 = _sha256(body)
    extension = 'png' if metadata['format'] == 'PNG' else 'jpg'
    content_type = 'image/png' if extension == 'png' else 'image/jpeg'
    key = 'geollaqta/maestro/raster/' + sha256 + '.' + extension
    state = _state({
        'center': metadata['center'],
        'width_m': metadata['initial_width_m'],
        'height_m': metadata['initial_height_m'],
        'rotation_deg': metadata['initial_rotation_deg'],
        'opacity': 1.0,
        'visible': True,
        'locked': False,
    })
    overlay_id = SOURCE_PREFIX + sha256[:24]
    original = {
        'name': filename,
        'sha256': sha256,
        'content_type': content_type,
        'object_key': key,
        'archive_status': 'verified_r2',
    }
    payload = _payload(overlay_id, name.strip(), ubigeo, metadata, state, original, 'Carga')
    if cloud is not None:
        cloud.put_verified(key, body, content_type)
    elif store.__class__.__module__.endswith('master_d1'):
        R2().put_verified(key, body, content_type)
    else:
        _memory_images[key] = body
    store.stage(payload, store.revision, actor)
    return _find(store, ubigeo, overlay_id)


def _find(store, ubigeo, overlay_id):
    identifier(overlay_id)
    overlay = next((item for item in _latest(store, ubigeo) if item['id'] == overlay_id), None)
    if not overlay:
        raise ValueError('La capa satelital no existe en este distrito.')
    return overlay


def calibrate(store, overlay_id, value, ubigeo, actor='sistema'):
    overlay = _find(store, ubigeo, overlay_id)
    state = _state(value, overlay['state'])
    payload = _payload(
        overlay_id, overlay['name'], ubigeo, overlay['metadata'], state,
        overlay['original'], 'Ajuste', datetime.now(timezone.utc).isoformat())
    store.stage(payload, store.revision, actor)
    return _find(store, ubigeo, overlay_id)


def image_body(store, overlay_id, ubigeo, cloud=None):
    overlay = _find(store, ubigeo, overlay_id)
    original = overlay['original']
    key = original.get('object_key', '')
    if not OBJECT_PATTERN.fullmatch(key):
        raise ValueError('La ruta de la imagen no es válida.')
    body = _memory_images.get(key)
    if body is None:
        body, _ = (cloud or R2()).get(key)
    if _sha256(body) != original.get('sha256'):
        raise StorageError('La imagen archivada no coincide con su huella SHA-256.')
    return body, original.get('content_type') or 'image/jpeg'
