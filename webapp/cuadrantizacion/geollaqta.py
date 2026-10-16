"""Read-only, district-scoped COFOPRI cadastral data for reusable map clients.

No properties, zones or upstream data are written. Gallery URLs come from the
lot's actual report; we never infer a photograph URL from a cadastral code.
"""
import math
import re
import json
import os
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_GET

DISTRICT = '040126'
DISTRICT_NAME = 'Yanahuara'
CATALOG = json.loads(Path(__file__).with_name('geollaqta_districts.json').read_text(encoding='utf-8'))
DISTRICTS = {entry['ubigeo']: entry for entry in CATALOG['districts']}
SERVICE = 'https://geoportal.cofopri.gob.pe/giscofopri/rest/services/Cofopri/Catastro_PCDPI/MapServer/10'
SERVICE_BASE = SERVICE.rsplit('/', 1)[0]
PORTAL = 'https://catastro.cofopri.gob.pe/geollaqta/'
FIELDS = 'OBJECTID,ID_LOTE,ID_DIST,COD_LOTE,COD_MZNA,COD_SECT,AREA_TER,AREA_CON,NIVELES,ANIO_CAT,NRO_UNIDADES'
LIMIT = 1000
LAYERS = {
    'ejes-vias': {'id': 0, 'name': 'Ejes de vías', 'kind': 'line', 'district_field': 'ID_UBI_GEO', 'fields': 'OBJECTID,ID_UBI_GEO,COD_VIA,TIP_VIA,NOM_VIA'},
    'ingresos': {'id': 1, 'name': 'Ingresos', 'kind': 'point', 'fields': 'OBJECTID,ID_LOTE,ID_DIST,COD_INGRES,TIPO'},
    'lotes': {'id': 10, 'name': 'Lotes', 'kind': 'polygon', 'fields': FIELDS},
    'manzanas': {'id': 11, 'name': 'Manzanas', 'kind': 'polygon', 'fields': 'OBJECTID,ID_DIST,COD_MZNA,COD_SECT,ID_MZNA,ANIO_CAT'},
    'comercios': {'id': 9, 'name': 'Comercios', 'kind': 'polygon', 'fields': 'OBJECTID,ID_DIST,ID_LOTE,COD_USO,DESC_USO,COD_PISO,ANIO_CAT'},
    'habilitaciones': {'id': 12, 'name': 'Habilitaciones urbanas', 'kind': 'polygon', 'fields': 'OBJECTID,ID_DIST,NOM_HAB_UR,NOM_PUEBLO,ID_HABILITACION'},
    'sectores': {'id': 13, 'name': 'Sectores', 'kind': 'polygon', 'fields': 'OBJECTID,ID_DIST,COD_SECTOR,ID_SECTOR'},
}
for floor in range(1, 7):
    LAYERS[f'piso-{floor}'] = {'id': 9 - floor, 'name': f'Construcciones · piso {floor}', 'kind': 'polygon',
                             'fields': 'OBJECTID,ID_DIST,ID_LOTE,COD_EDIFICACION,COD_PISO,ANIO_CAT'}


class UpstreamError(Exception):
    pass


def _district(request):
    code = request.GET.get('ubigeo', DISTRICT)
    if code not in DISTRICTS:
        raise ValueError('Elige un distrito del catálogo catastral de Arequipa.')
    return DISTRICTS[code]


@require_GET
def districts(request):
    if not _authenticated(request):
        return JsonResponse({'error': 'Inicia sesión para consultar el catastro.'}, status=401)
    return JsonResponse({**CATALOG, 'layers': LAYERS,
                         'districts_with_lots': sum(entry['published_lots'] > 0 for entry in DISTRICTS.values()),
                         'total_lots': sum(entry['published_lots'] for entry in DISTRICTS.values())})


def _authenticated(request):
    return any(user and getattr(user, 'is_active', False) and
               getattr(user, 'is_authenticated', False)
               for user in (getattr(request, 'current_user', None), getattr(request, 'user', None)))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _download(url, params=None):
    """Use Python's system trust store, including Windows enterprise roots."""
    try:
        request = Request(url, data=urlencode(params).encode() if params is not None else None)
        with build_opener(_NoRedirect()).open(request, timeout=15) as response:
            body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise UpstreamError('La respuesta de COFOPRI es demasiado grande. Acércate al mapa.')
        return body
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise UpstreamError('COFOPRI no está disponible. Intenta actualizar en unos minutos.') from exc


def _query(layer=10, **params):
    try:
        data = json.loads(_download(SERVICE_BASE + f'/{layer}/query', {'f': 'json', **params}))
        if not isinstance(data, dict) or data.get('error'):
            raise UpstreamError('COFOPRI no pudo completar la consulta.')
        return data
    except (ValueError, UnicodeError) as exc:
        raise UpstreamError('COFOPRI no está disponible. Intenta actualizar en unos minutos.') from exc


def _bbox(value):
    try:
        box = tuple(float(part) for part in value.split(','))
    except (ValueError, AttributeError):
        raise ValueError('Indica un área válida del mapa.')
    if len(box) != 4 or not all(math.isfinite(number) for number in box):
        raise ValueError('Indica un área válida del mapa.')
    west, south, east, north = box
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError('Indica un área válida del mapa.')
    if east - west > .05 or north - south > .05:
        raise ValueError('Acércate al mapa para consultar los lotes.')
    # Quantization improves reuse while slightly expanding the requested bounds.
    return (math.floor(west * 1e5) / 1e5, math.floor(south * 1e5) / 1e5,
            math.ceil(east * 1e5) / 1e5, math.ceil(north * 1e5) / 1e5)


def _in_ring(point, ring):
    inside = False
    x, y = point
    for a, b in zip(ring, ring[1:]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return inside


def _geometry(geometry):
    """Convert Esri rings by containment, preserving holes and disjoint parts."""
    rings = []
    for raw in geometry.get('rings', []):
        if not isinstance(raw, list) or not 3 <= len(raw) <= 2000:
            raise ValueError('Invalid ring')
        ring = []
        for point in raw:
            x, y = float(point[0]), float(point[1])
            if not (math.isfinite(x) and math.isfinite(y) and -180 <= x <= 180 and -90 <= y <= 90):
                raise ValueError('Invalid coordinate')
            ring.append([x, y])
        if ring[0] != ring[-1]:
            ring.append(ring[0][:])
        area = abs(sum((a[0] - ring[0][0]) * (b[1] - ring[0][1]) -
                       (b[0] - ring[0][0]) * (a[1] - ring[0][1])
                       for a, b in zip(ring, ring[1:])))
        if not area:
            raise ValueError('Empty polygon')
        rings.append((area, ring))
    if not rings or len(rings) > 64:
        raise ValueError('Invalid polygon')
    rings.sort(key=lambda item: item[0], reverse=True)
    parents, depths, polygons, owners = [], [], [], {}
    for index, (_, ring) in enumerate(rings):
        enclosing = [i for i in range(index) if _in_ring(ring[0], rings[i][1])]
        parent = enclosing[-1] if enclosing else None
        parents.append(parent)
        depth = depths[parent] + 1 if parent is not None else 0
        depths.append(depth)
        if depth % 2 == 0:
            owners[index] = len(polygons)
            polygons.append([ring])
        else:
            polygons[owners[parent]].append(ring)
    if len(polygons) == 1:
        return {'type': 'Polygon', 'coordinates': polygons[0]}
    return {'type': 'MultiPolygon', 'coordinates': polygons}


def _esri_geometry(geometry, kind):
    if kind == 'polygon':
        return _geometry(geometry)
    def point(raw):
        x, y = float(raw[0]), float(raw[1])
        if not (math.isfinite(x) and math.isfinite(y) and -180 <= x <= 180 and -90 <= y <= 90):
            raise ValueError('Invalid coordinate')
        return [x, y]
    if kind == 'point':
        return {'type': 'Point', 'coordinates': point([geometry['x'], geometry['y']])}
    paths = geometry.get('paths', [])
    if not paths or any(not 2 <= len(path) <= 2000 for path in paths):
        raise ValueError('Invalid path')
    lines = [[point(raw) for raw in path] for path in paths]
    return {'type': 'LineString', 'coordinates': lines[0]} if len(lines) == 1 else {'type': 'MultiLineString', 'coordinates': lines}


def _properties(attributes, fields=FIELDS):
    return {key: value.strip() if isinstance(value, str) else value
            for key, value in attributes.items() if key in fields.split(',')}


class GalleryParser(HTMLParser):
    def __init__(self, district=DISTRICT):
        super().__init__()
        self.district = district
        self.images, self.records = [], []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'img':
            url = urljoin(PORTAL, attributes.get('src', ''))
            parsed = urlsplit(url)
            if (parsed.scheme == 'https' and parsed.netloc == 'catastro.cofopri.gob.pe'
                    and re.fullmatch(rf'/img_catastro/{self.district}/[A-Za-z0-9_.-]+\.(?:jpg|jpeg|png)', parsed.path, re.I)
                    and not parsed.query and url not in self.images):
                self.images.append(url)
        if tag == 'a':
            url = urljoin(PORTAL, attributes.get('href', ''))
            parsed = urlsplit(url)
            if (parsed.scheme == 'https' and parsed.netloc == 'catastro.cofopri.gob.pe'
                    and parsed.path == '/geollaqta/reportefichas/vistapdf/fichain.php'
                    and re.fullmatch(rf'id={self.district}\d{{13}}', parsed.query)
                    and url not in self.records):
                self.records.append(url)


def _gallery(lot_id):
    key = 'geollaqta-gallery-v1:' + lot_id
    result = cache.get(key)
    if result is not None:
        return result
    url = PORTAL + 'reportefichas/vistadetalle.php?' + urlencode({'id_lote': lot_id})
    try:
        parser = GalleryParser(lot_id[:6])
        parser.feed(_download(url).decode('utf-8', errors='replace'))
        result = {'images': parser.images[:12], 'records': parser.records[:12], 'gallery_status': 'available'}
        cache.set(key, result, 3600)
        return result
    except (ValueError, UnicodeError) as exc:
        raise UpstreamError('No se pudo consultar la galería de COFOPRI.') from exc


@require_GET
def coverage(request):
    if not _authenticated(request):
        return JsonResponse({'error': 'Inicia sesión para consultar el catastro.'}, status=401)
    try:
        entry = _district(request)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    district, name = entry['ubigeo'], entry['name']
    metadata = {'district': name, 'ubigeo': district, 'center': entry['center'],
                'sample_lot': entry['sample_lot'], 'reference_total': entry['published_lots'],
                'checked_at': CATALOG['checked_at']}
    # COFOPRI's service accepts browser CORS, while the Azure outbound IP
    # cannot currently connect. Authorize the UI and provide the same fixed
    # layer allowlist; the browser queries public geometry and embeds reports.
    if os.environ.get('WEBSITE_SITE_NAME') or request.GET.get('transport') == 'browser':
        return JsonResponse({**metadata,
                             'transport': 'browser', 'service_base': SERVICE_BASE,
                             'layers': LAYERS})
    if request.GET.get('metadata') == '1':
        return JsonResponse({**metadata, 'transport': 'server', 'layers': LAYERS})
    try:
        key = f'geollaqta-coverage-v3:{district}'
        result = cache.get(key)
        if result is None:
            data = _query(where=f"ID_DIST='{district}'", returnCountOnly='true')
            if not isinstance(data.get('count'), int):
                raise UpstreamError('No se pudo verificar la cobertura de COFOPRI.')
            result = {**metadata, 'total': data['count'], 'transport': 'server',
                      'source': SERVICE,
                      'layers': [{'key': key, 'name': value['name']} for key, value in LAYERS.items()]}
            cache.set(key, result, 900)
        return JsonResponse(result)
    except UpstreamError as exc:
        return JsonResponse({'error': str(exc)}, status=502)


@require_GET
def lots(request):
    return layer(request, 'lotes')


@require_GET
def layer(request, layer_key):
    if not _authenticated(request):
        return JsonResponse({'error': 'Inicia sesión para consultar el catastro.'}, status=401)
    config = LAYERS.get(layer_key)
    if not config:
        return JsonResponse({'error': 'Capa catastral no disponible.'}, status=404)
    district_field = config.get('district_field', 'ID_DIST')
    try:
        entry = _district(request)
        box = _bbox(request.GET.get('bbox'))
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    district = entry['ubigeo']
    key = f'geollaqta-layer-v3:{district}:{layer_key}:' + ','.join(map(str, box))
    result = cache.get(key)
    if result is not None:
        return JsonResponse(result)
    try:
        # ArcGIS 10.3 does not support pagination: enumerate IDs in the viewport
        # first, then fetch explicit, bounded batches instead of silently truncating.
        data = _query(layer=config['id'], where=f"{district_field}='{district}'", geometry=','.join(map(str, box)),
                      geometryType='esriGeometryEnvelope', inSR=4326,
                      spatialRel='esriSpatialRelIntersects', returnIdsOnly='true')
        ids = sorted(set(data.get('objectIds') or []))
        selected, features, skipped = ids[:LIMIT], [], 0
        for start in range(0, len(selected), 500):
            batch = _query(layer=config['id'], objectIds=','.join(map(str, selected[start:start + 500])),
                           outFields=config['fields'], returnGeometry='true', outSR=4326)
            if 'features' not in batch:
                raise UpstreamError('COFOPRI devolvió una respuesta incompleta.')
            for row in batch['features']:
                attrs = _properties(row.get('attributes', {}), config['fields'])
                if attrs.get(district_field) != district:
                    continue
                try:
                    geometry = _esri_geometry(row.get('geometry') or {}, config['kind'])
                except (ValueError, TypeError, IndexError, KeyError):
                    skipped += 1
                    continue
                features.append({'type': 'Feature', 'id': attrs['OBJECTID'],
                                 'properties': attrs, 'geometry': geometry})
        result = {'type': 'FeatureCollection', 'features': features, 'district': entry['name'], 'ubigeo': district,
                  'total_in_view': len(ids), 'truncated': len(ids) > LIMIT, 'skipped': skipped,
                  'source': SERVICE_BASE + '/' + str(config['id']), 'layer': layer_key, 'name': config['name']}
        cache.set(key, result, 300)
        return JsonResponse(result)
    except UpstreamError as exc:
        return JsonResponse({'error': str(exc)}, status=502)


@require_GET
def detail(request, object_id):
    if not _authenticated(request):
        return JsonResponse({'error': 'Inicia sesión para consultar el catastro.'}, status=401)
    try:
        entry = _district(request)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    district = entry['ubigeo']
    key = f'geollaqta-detail-v2:{district}:{int(object_id)}'
    saved = cache.get(key)
    if saved is not None:
        return JsonResponse(saved)
    try:
        data = _query(where=f"OBJECTID={int(object_id)} AND ID_DIST='{district}'",
                      outFields=FIELDS, returnGeometry='false')
        rows = data.get('features', [])
        if not rows:
            return JsonResponse({'error': 'El lote no pertenece al distrito seleccionado.'}, status=404)
        attrs = _properties(rows[0]['attributes'])
        if attrs.get('ID_DIST') != district:
            return JsonResponse({'error': 'El lote no pertenece al distrito seleccionado.'}, status=404)
        lot_id = attrs.get('ID_LOTE', '')
        if not re.fullmatch(rf'{district}\d{{8,12}}', lot_id):
            raise UpstreamError('COFOPRI no devolvió un código de lote válido.')
        result = {'properties': attrs, 'district': entry['name'], 'ubigeo': district,
                  'gallery_url': PORTAL + 'reportefichas/vistadetalle.php?' + urlencode({'id_lote': lot_id})}
        try:
            result.update(_gallery(lot_id))
        except UpstreamError as exc:
            # Keep cadastral metadata useful when the separate report service fails.
            result.update(images=[], records=[], gallery_status='unavailable', gallery_error=str(exc))
        if result.get('gallery_status') != 'unavailable':
            cache.set(key, result, 900)
        return JsonResponse(result)
    except UpstreamError as exc:
        return JsonResponse({'error': str(exc)}, status=502)


@require_GET
def report(request, lot_id):
    if not _authenticated(request):
        return JsonResponse({'error': 'Inicia sesión para consultar el catastro.'}, status=401)
    try:
        district = _district(request)['ubigeo']
        record_id = request.GET.get('record_id') or None
        if not re.fullmatch(district + r'\d{8,12}', lot_id):
            raise ValueError('El lote no pertenece al distrito seleccionado.')
        if record_id and not re.fullmatch(district + r'\d{13}', record_id):
            raise ValueError('El reporte no pertenece al distrito seleccionado.')
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    from catastro.map_report import report_cache_key
    key = report_cache_key(lot_id, record_id)
    saved = cache.get(key)
    if saved is not None:
        response = JsonResponse(saved)
        response['Cache-Control'] = 'private, no-store'
        return response
    from catastro.map_report import report_measurements, ReportUnavailable
    from scrapi.geollaqta_scraper import CollectionError
    try:
        result = report_measurements(lot_id, record_id)
        cache.set(key, result, 900)
        response = JsonResponse(result)
        response['Cache-Control'] = 'private, no-store'
        return response
    except (ReportUnavailable, CollectionError, ValueError, RuntimeError):
        return JsonResponse({'error': 'No se pudo leer el reporte del lote. Las áreas y medidas quedan sin verificar.'}, status=502)
