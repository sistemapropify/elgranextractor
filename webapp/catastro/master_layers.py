"""Source-aware geometry catalogue for the master cadastre.

The common format is GeoJSON/WGS84. Source IDs are namespaced; unknown cadastral
codes stay null. A reference polygon never becomes a COFOPRI report identity.
Files here are curated application layers, not collector downloads or state.
"""
import json
import math
from functools import lru_cache
from pathlib import Path

from cuadrantizacion import geollaqta as geo
from . import source_placement

DATA = Path(__file__).with_name('data')
SOURCES = {'cayma-pud-2006-eu03': DATA / 'cayma-pud-2006-eu03'}
SCHEMA = 'prometeo-cadastral-geometry-v1'


@lru_cache(maxsize=4)
def _read(path, modified):
    return json.loads(Path(path).read_text(encoding='utf8'))


def read(path):
    return _read(str(path), path.stat().st_mtime_ns)


def source_metadata(source_id):
    folder = SOURCES[source_id]
    meta = read(folder/'metadata.json')
    placement = {key: value for key, value in source_placement.read(folder).items()
                 if key in ('revision', 'east_m', 'north_m', 'blocks', 'locked', 'updated_at')}
    dx, dy = source_placement.degrees(placement, (meta['bbox'][1]+meta['bbox'][3])/2)
    bounds = [meta['bbox'][0]+dx, meta['bbox'][1]+dy, meta['bbox'][2]+dx, meta['bbox'][3]+dy]
    # Include moved/scaled blocks so radius providers cannot discard their new location.
    if placement.get('blocks'):
        path = folder/'manzanas.geojson'
        placed = _placed(str(path), path.stat().st_mtime_ns, json.dumps(placement, sort_keys=True),
                         (meta['bbox'][1]+meta['bbox'][3])/2)
        for feature in placed['features']:
            polygons = [feature['geometry']['coordinates']] if feature['geometry']['type'] == 'Polygon' else feature['geometry']['coordinates']
            for polygon in polygons:
                for ring in polygon:
                    for p in ring:
                        bounds = [min(bounds[0], p[0]), min(bounds[1], p[1]), max(bounds[2], p[0]), max(bounds[3], p[1])]
    return {**meta, 'placement': placement,
            'bbox': bounds, 'original_bbox': meta['bbox']}


def revisions():
    return {source_id: source_placement.read(folder)['revision'] for source_id, folder in SOURCES.items()
            if (folder/'metadata.json').is_file() and read(folder/'metadata.json').get('active')}


@lru_cache(maxsize=4)
def _placed(path, modified, serialized, latitude):
    original = _read(path, modified)
    placement = json.loads(serialized)
    if not placement['east_m'] and not placement['north_m'] and not placement.get('blocks'):
        return original
    dx, dy = source_placement.degrees(placement, latitude)
    pivots = source_placement.anchors(Path(path).parent)
    def placed(feature):
        block_id = feature['properties'].get('BLOCK_REF') or feature['id']
        edit = placement.get('blocks', {}).get(block_id)
        scale = edit['scale'] if edit else 1
        cx, cy = pivots.get(block_id, (0, 0))
        bx, by = source_placement.degrees(edit, latitude) if edit else (0, 0)
        def transform(value):
            if isinstance(value[0], (int, float)):
                return [round(cx+(value[0]-cx)*scale+bx+dx, 8), round(cy+(value[1]-cy)*scale+by+dy, 8)]
            return [transform(v) for v in value]
        return {**feature, 'geometry': {**feature['geometry'], 'coordinates': transform(feature['geometry']['coordinates'])},
                'properties': {**feature['properties'], 'PLACEMENT_REVISION': placement['revision']}}
    return {**original, 'features': [placed(f) for f in original['features']]}


def catalogue():
    sources = [{
        'id': 'geollaqta', 'name': 'GeoLlaqta · COFOPRI', 'active': True,
        'status': 'published', 'reference_only': False, 'crs': 'EPSG:4326',
        'transport': 'arcgis', 'service_base': geo.SERVICE_BASE,
        'layers': {key: config for key, config in geo.LAYERS.items()
                   if key in ('lotes', 'manzanas')},
        'districts': [d['ubigeo'] for d in geo.DISTRICTS.values() if d['published_lots']],
    }]
    for source_id, folder in SOURCES.items():
        if (folder/'metadata.json').is_file():
            sources.append({**source_metadata(source_id), 'transport': 'master',
                            'districts': [read(folder/'metadata.json')['ubigeo']]})
    districts = [{**d} for d in geo.DISTRICTS.values()]
    for district in districts:
        district['sources'] = [s['id'] for s in sources if district['ubigeo'] in s['districts']]
        if district['ubigeo'] == '040103':
            district['center'] = {'lat': -16.359, 'lng': -71.545}
    return {'revision': 1, 'schema': SCHEMA, 'crs': 'EPSG:4326',
            'layers': [{'key': 'manzanas', 'name': 'Manzanas'}, {'key': 'lotes', 'name': 'Lotes'}],
            'districts': districts, 'sources': sources}


def bbox(value):
    if not value:
        return None
    try:
        values = [float(v) for v in value.split(',')]
        if (len(values) != 4 or not all(math.isfinite(v) for v in values)
                or not -180 <= values[0] < values[2] <= 180
                or not -90 <= values[1] < values[3] <= 90):
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('Extensión geográfica no válida.') from None
    return values


def intersects(geometry, bounds):
    # Bounding-box prefilter preserves complete original polygons, including
    # polygons that cross or contain the requested viewport.
    polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
    points = [p for polygon in polygons for ring in polygon for p in ring]
    return (min(p[0] for p in points) <= bounds[2]
            and max(p[0] for p in points) >= bounds[0]
            and min(p[1] for p in points) <= bounds[3]
            and max(p[1] for p in points) >= bounds[1])


def layer(source_id, key, district, bounds=None, *, original=False, metadata=None):
    if source_id not in SOURCES or key not in ('lotes', 'manzanas'):
        raise ValueError('Fuente o capa no disponible.')
    folder = SOURCES[source_id]
    meta = metadata if metadata is not None else source_metadata(source_id)
    if not meta['active'] or district != meta['ubigeo']:
        raise ValueError('La fuente no está activa para este distrito.')
    path = folder/(key+'.geojson')
    raw_meta = read(folder/'metadata.json')
    placement = meta['placement']
    value = read(path) if original else _placed(str(path), path.stat().st_mtime_ns,
                    json.dumps(placement, sort_keys=True), (raw_meta['bbox'][1]+raw_meta['bbox'][3])/2)
    features = value['features']
    if bounds:
        features = [f for f in features if intersects(f['geometry'], bounds)]
    return {**value, 'features': features, 'total': len(features),
            'source_total': len(value['features']), 'complete': True,
            'reference_only': meta['reference_only'], 'crs': meta['crs'],
            'bbox': meta['bbox'], 'original_bbox': raw_meta['bbox'], 'original': original,
            'placement': placement, 'schema': SCHEMA}


def radius(source_id, lat, lng, metres):
    """Whole polygons intersecting a small circle; no GIS runtime is needed."""
    lat, lng, metres = float(lat), float(lng), float(metres)
    if (not all(math.isfinite(v) for v in (lat, lng, metres))
            or not -85 <= lat <= 85 or not -180 <= lng <= 180 or not 100 <= metres <= 2000):
        raise ValueError('Ubicación o radio no válido.')
    if source_id not in SOURCES:
        raise ValueError('Fuente no disponible.')
    meta = source_metadata(source_id)
    sy = 6371008.8 * math.pi/180
    sx = sy * math.cos(math.radians(lat))
    bounds = [lng-metres/sx, lat-metres/sy, lng+metres/sx, lat+metres/sy]
    def inside(ring):
        hit = False
        for a, b in zip(ring, ring[1:]):
            if (a[1] > lat) != (b[1] > lat) and lng < (b[0]-a[0])*(lat-a[1])/(b[1]-a[1])+a[0]:
                hit = not hit
        return hit
    def touches(geometry):
        polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
        for rings in polygons:
            if inside(rings[0]) and not any(inside(r) for r in rings[1:]):
                return True
            for ring in rings:
                for a, b in zip(ring, ring[1:]):
                    ax, ay, bx, by = (a[0]-lng)*sx, (a[1]-lat)*sy, (b[0]-lng)*sx, (b[1]-lat)*sy
                    dx, dy = bx-ax, by-ay
                    t = max(0, min(1, -(ax*dx+ay*dy)/(dx*dx+dy*dy or 1)))
                    if (ax+t*dx)**2+(ay+t*dy)**2 <= (metres+0.1)**2:
                        return True
        return False
    result = {}
    for key, label in [('lotes', 'lots'), ('manzanas', 'blocks')]:
        candidates = layer(source_id, key, meta['ubigeo'], bounds, metadata=meta)
        result[label] = {**candidates, 'features': [f for f in candidates['features'] if touches(f['geometry'])]}
        result[label]['total'] = len(result[label]['features'])
    return {**result, 'source_id': source_id, 'reference_only': True, 'complete': True,
            'center': {'lat': lat, 'lng': lng}, 'radius': metres, 'schema': SCHEMA}
