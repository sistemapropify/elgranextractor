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
SOURCES = {
    'cayma-pud-2006-eu03': DATA / 'cayma-pud-2006-eu03',
    'cayma-sector-32-provisional': DATA / 'cayma-sector-32-provisional',
}
CAYMA_2006 = 'cayma-pud-2006-eu03'
SECTOR32 = 'cayma-sector-32-provisional'
SCHEMA = 'prometeo-cadastral-geometry-v1'


@lru_cache(maxsize=1)
def _sector32_mask(modified):
    from shapely.geometry import shape
    from shapely.ops import unary_union
    folder = SOURCES[SECTOR32]
    polygons = []
    for name, buffer_m in (('manzanas.geojson', 14), ('lotes.geojson', 2)):
        data = read(folder / name)
        for feature in data['features']:
            geometry = shape(feature['geometry'])
            if not geometry.is_empty:
                # Degrees are converted locally; approximately 1 degree = 111 km.
                polygons.append(geometry.buffer(buffer_m / 111000))
    return unary_union(polygons) if polygons else None


def _without_sector32(feature):
    """Subtract Sector 32 priority coverage from the 2006 backup geometry."""
    from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping, shape
    from shapely.ops import unary_union
    folder = SOURCES[SECTOR32]
    modified = max((folder / 'lotes.geojson').stat().st_mtime_ns,
                   (folder / 'manzanas.geojson').stat().st_mtime_ns)
    mask = _sector32_mask(modified)
    if mask is None:
        return feature
    geometry = shape(feature['geometry'])
    if not geometry.intersects(mask):
        return feature
    remaining = geometry.difference(mask)
    if isinstance(remaining, GeometryCollection):
        remaining = unary_union([
            part for part in remaining.geoms
            if isinstance(part, (Polygon, MultiPolygon)) and not part.is_empty
        ])
    if not isinstance(remaining, (Polygon, MultiPolygon)) or remaining.area <= 1e-16:
        return None
    if not remaining.is_valid:
        remaining = remaining.buffer(0)
    if remaining.is_empty or not isinstance(remaining, (Polygon, MultiPolygon)):
        return None
    return {**feature, 'geometry': mapping(remaining)}


def _draft_metadata(source_id, summary=None):
    import re
    from . import source_manager
    if not (source_manager.enabled() or source_manager.durable()) or not re.fullmatch(r'borrador-[0-9]{6}', source_id):
        raise ValueError('Fuente no disponible.')
    district = source_id[-6:]
    summary = summary or source_manager.district_summary(district)
    if not summary or not (summary.get('lotes') or summary.get('manzanas')):
        raise ValueError('El borrador todavía no tiene geometrías activas en este distrito.')
    district_name=(geo.DISTRICTS.get(district) or {}).get('name',district)
    return {'id':source_id,'name':'Catastro Maestro · '+district_name,'ubigeo':district,'districts':[district],
            'active':True,'default_visible':True,'contributes':True,'reference_only':False,
            'role':'draft','status':'active_master','transport':'master','crs':'EPSG:4326',
            'bbox':summary.get('bbox'),'original_bbox':summary.get('bbox'),
            'revision':summary['revision'],
            'placement':{'revision':summary['revision'],'east_m':0.,'north_m':0.,'locked':True},
            'layers':{'lotes':{'count':summary['lotes'],'kind':'polygon'},
                      'manzanas':{'count':summary['manzanas'],'kind':'polygon'}}}


@lru_cache(maxsize=4)
def _read(path, modified):
    return json.loads(Path(path).read_text(encoding='utf8'))


def read(path):
    return _read(str(path), path.stat().st_mtime_ns)


def source_metadata(source_id, summary=None):
    if source_id.startswith('borrador-'):
        return _draft_metadata(source_id, summary)
    folder = SOURCES[source_id]
    meta = read(folder/'metadata.json')
    if source_id == SECTOR32:
        # The provisional PDF was already georeferenced as immutable GeoJSON.
        placement = {'revision': 0, 'east_m': 0., 'north_m': 0.,
                     'blocks': {}, 'locked': True}
    else:
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
    value = {}
    for source_id, folder in SOURCES.items():
        metadata_path = folder / 'metadata.json'
        if not metadata_path.is_file():
            continue
        metadata = read(metadata_path)
        if not metadata.get('active'):
            continue
        if source_id == SECTOR32:
            value[source_id] = 0
        else:
            value[source_id] = source_placement.read(folder)['revision']
    from . import source_manager
    if source_manager.enabled() or source_manager.durable():
        for district, summary in source_manager.district_summaries().items():
            value['borrador-'+district] = summary['revision']
    return value


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
    from . import source_manager
    if source_manager.enabled() or source_manager.durable():
        for district, summary in source_manager.district_summaries().items():
            sources.append(_draft_metadata('borrador-'+district, summary))
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


def public_draft_layer(value):
    """Map permission does not grant the administrative documentary record."""
    allowed = {'ID_DIST','ID_LOTE','ID_MZNA','COD_SECT','COD_MZNA','COD_LOTE','ELEMENT_ID','SOURCE_ID',
               'SOURCE_NAME','MASTER_LAYER','REFERENCE_ONLY','GEOMETRY_VERSION_ID','BLOCK_REF'}
    return {**value, 'features':[{'type':'Feature','id':feature['id'],'geometry':feature['geometry'],
             'properties':{k:v for k,v in feature.get('properties',{}).items() if k in allowed}}
             for feature in value['features']]}


def layer(source_id, key, district, bounds=None, *, original=False, metadata=None):
    if source_id.startswith('borrador-'):
        from . import source_manager
        if not (source_manager.enabled() or source_manager.durable()):
            raise ValueError('Fuente no disponible.')
        return _layer(source_id, key, district, bounds, original=original, metadata=metadata)
    return _layer(source_id, key, district, bounds, original=original, metadata=metadata)


def _layer(source_id, key, district, bounds=None, *, original=False, metadata=None):
    if source_id.startswith('borrador-'):
        if key not in ('lotes','manzanas') or district != source_id[-6:] or original:
            raise ValueError('Fuente, capa o distrito no válido.')
        from . import source_manager
        meta = metadata if metadata is not None else _draft_metadata(source_id)
        data = source_manager.collection(
            district, 'lote' if key=='lotes' else 'manzana',
            revision=meta.get('revision'))
        features = []
        aliases = {'ubigeo':'ID_DIST','sector':'COD_SECT','block':'COD_MZNA','lot':'COD_LOTE'}
        for feature in data['features']:
            if bounds and not intersects(feature['geometry'],bounds):
                continue
            attrs = {**feature['properties'], 'ELEMENT_ID':feature['id'], 'SOURCE_ID':source_id,
                     'REFERENCE_ONLY':False, 'MASTER_LAYER':key,
                     'GEOMETRY_VERSION_ID':feature['provenance'].get('$geometry',{}).get('version_id')}
            attrs.update({target:attrs.get(source) for source,target in aliases.items()})
            source_feature_id = attrs.pop('source_feature_id', None)
            if source_feature_id:
                attrs['ID_LOTE' if key=='lotes' else 'ID_MZNA'] = str(source_feature_id)
            features.append({**feature,'id':source_id+':'+feature['id'],'properties':attrs})
        return {**data,'features':features,'total':len(features),'source_total':len(data['features']),
                'complete':True,'reference_only':False,'bbox':meta['bbox'],'original_bbox':meta['bbox'],
                'original':False,'placement':meta['placement'],'schema':SCHEMA}
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
    if source_id == CAYMA_2006:
        features = [filtered for feature in features
                    if (filtered := _without_sector32(feature)) is not None]
    return {**value, 'features': features, 'total': len(features),
            'source_total': len(value['features']), 'complete': True,
            'reference_only': meta['reference_only'], 'crs': meta['crs'],
            'bbox': meta['bbox'], 'original_bbox': raw_meta['bbox'], 'original': original,
            'placement': placement, 'schema': SCHEMA}


def radius(source_id, lat, lng, metres):
    if source_id.startswith('borrador-'):
        from . import source_manager
        if not (source_manager.enabled() or source_manager.durable()):
            raise ValueError('Fuente no disponible.')
        return _radius(source_id, lat, lng, metres)
    return _radius(source_id, lat, lng, metres)


def _radius(source_id, lat, lng, metres):
    """Whole polygons intersecting a small circle; no GIS runtime is needed."""
    lat, lng, metres = float(lat), float(lng), float(metres)
    if (not all(math.isfinite(v) for v in (lat, lng, metres))
            or not -85 <= lat <= 85 or not -180 <= lng <= 180 or not 100 <= metres <= 2000):
        raise ValueError('Ubicación o radio no válido.')
    if source_id not in SOURCES and not source_id.startswith('borrador-'):
        raise ValueError('Fuente no disponible.')
    summary = None
    if source_id.startswith('borrador-'):
        from . import source_manager
        summary = source_manager.district_summary(source_id[-6:])
    meta = source_metadata(source_id, summary)
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
    return {**result, 'source_id': source_id, 'reference_only': meta['reference_only'], 'complete': True,
            'center': {'lat': lat, 'lng': lng}, 'radius': metres, 'schema': SCHEMA}
