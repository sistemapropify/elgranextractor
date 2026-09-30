"""Conservative spatial admission over immutable ZonaValor snapshots.

Coordinates follow the project's internal ``[[latitude, longitude], ...]``
format, not GeoJSON. Only zona/subzona/cuadrante can be a selected microzone.
An exact coordinate is a portal declaration, never cadastral certification.

This is planar point-in-polygon for local polygons, without holes. Rings which
cross the antimeridian are rejected. EPS is a numerical tolerance in degrees
(about 0.1 mm), not an estimate of GPS accuracy. One closing vertex is allowed;
internal repeated vertices, self intersections and zero-area rings are not.

No row or zone is mutated, and neither price nor district text participates in
assignment. Polygon validation and nesting checks have bounded content caches.
"""
from collections.abc import Mapping
from functools import lru_cache
import math


SPATIAL_RULE_VERSION = 'spatial-geometry-v1'
EPS = 1e-9
LEVELS = ('pais', 'departamento', 'provincia', 'distrito', 'zona', 'subzona', 'cuadrante')
MICRO_LEVELS = frozenset(LEVELS[4:])


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    lat, lng = (_number(item) for item in value)
    if lat is None or lng is None or not -90 <= lat <= 90 or not -180 <= lng <= 180:
        return None
    return lat, lng


def _close(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= EPS


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(point, a, b):
    if not (min(a[0], b[0]) - EPS <= point[0] <= max(a[0], b[0]) + EPS
            and min(a[1], b[1]) - EPS <= point[1] <= max(a[1], b[1]) + EPS):
        return False
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    return _close(point, a) if length <= EPS else abs(_cross(a, b, point)) <= EPS * length


def _orientation(a, b, point):
    cross = _cross(a, b, point)
    tolerance = EPS * math.hypot(b[0] - a[0], b[1] - a[1])
    return 1 if cross > tolerance else -1 if cross < -tolerance else 0


def _intersects(a, b, c, d):
    first, second = _orientation(a, b, c), _orientation(a, b, d)
    third, fourth = _orientation(c, d, a), _orientation(c, d, b)
    if first * second < 0 and third * fourth < 0:
        return True
    return ((first == 0 and _on_segment(c, a, b))
            or (second == 0 and _on_segment(d, a, b))
            or (third == 0 and _on_segment(a, c, d))
            or (fourth == 0 and _on_segment(b, c, d)))


def _edges(ring):
    return zip(ring, ring[1:] + ring[:1])


def _bounds(ring):
    return (min(p[0] for p in ring), min(p[1] for p in ring),
            max(p[0] for p in ring), max(p[1] for p in ring)) if ring else None


def _in_bounds(point, bounds):
    return (bounds[0] - EPS <= point[0] <= bounds[2] + EPS
            and bounds[1] - EPS <= point[1] <= bounds[3] + EPS)


@lru_cache(maxsize=512)
def _validate_ring(points):
    ring = points[:-1] if len(points) > 1 and _close(points[0], points[-1]) else points
    bounds = _bounds(ring)
    if len(ring) < 3:
        return ring, bounds, 'too_few_vertices'
    for i, point in enumerate(ring):
        if any(_close(point, other) for other in ring[i + 1:]):
            return ring, bounds, 'repeated_vertex'
    edges = tuple(_edges(ring))
    for i, (a, b) in enumerate(edges):
        if abs(a[1] - b[1]) > 180:
            return ring, bounds, 'antimeridian_not_supported'
        previous = ring[i - 1]
        if _on_segment(previous, a, b) or _on_segment(b, previous, a):
            return ring, bounds, 'overlapping_adjacent_edges'
        for j in range(i + 1, len(edges)):
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if _intersects(a, b, *edges[j]):
                return ring, bounds, 'self_intersection'
    # Translate before summing to avoid cancellation at real Peru coordinates.
    area2 = abs(sum(_cross(ring[0], a, b) for a, b in edges))
    span = max(bounds[2] - bounds[0], bounds[3] - bounds[1])
    if area2 <= EPS * max(span, EPS):
        return ring, bounds, 'zero_area'
    return ring, bounds, None


def _geometry(coordinates):
    if not isinstance(coordinates, (list, tuple)):
        return (), None, 'missing_polygon' if coordinates is None else 'invalid_polygon_format'
    points = tuple(_point(value) for value in coordinates)
    if any(point is None for point in points):
        # A partly corrupt ring has no trustworthy spatial extent.
        return (), None, 'invalid_polygon_coordinate'
    return _validate_ring(points)


def _locate(point, ring, bounds=None):
    """Return outside, boundary or inside, independent of ring orientation."""
    if bounds is not None and not _in_bounds(point, bounds):
        return 'outside'
    inside = False
    x, y = point
    for a, b in _edges(ring):
        if _on_segment(point, a, b):
            return 'boundary'
        if (a[1] > y) != (b[1] > y):
            at_x = a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1])
            if x < at_x:
                inside = not inside
    return 'inside' if inside else 'outside'


def _edge_fractions(a, b, c, d):
    """Split a child edge at parent boundaries, including collinear contacts."""
    rx, ry = b[0] - a[0], b[1] - a[1]
    sx, sy = d[0] - c[0], d[1] - c[1]
    denominator = rx * sy - ry * sx
    length = math.hypot(rx, ry)
    tolerance = EPS / length
    cuts = []
    if abs(denominator) > EPS * max(length, math.hypot(sx, sy)):
        qx, qy = c[0] - a[0], c[1] - a[1]
        t = (qx * sy - qy * sx) / denominator
        u = (qx * ry - qy * rx) / denominator
        if -tolerance <= t <= 1 + tolerance and -EPS / math.hypot(sx, sy) <= u <= 1 + EPS / math.hypot(sx, sy):
            cuts.append(max(0.0, min(1.0, t)))
    for point in (c, d):
        if _on_segment(point, a, b):
            t = ((point[0] - a[0]) * rx + (point[1] - a[1]) * ry) / (length * length)
            cuts.append(max(0.0, min(1.0, t)))
    return cuts


@lru_cache(maxsize=512)
def _nested(child, parent):
    """Check whole child edges, not only vertices (parents may be concave)."""
    bounds = _bounds(parent)
    if any(_locate(point, parent, bounds) == 'outside' for point in child):
        return False
    for a, b in _edges(child):
        cuts = [0.0, 1.0]
        for c, d in _edges(parent):
            cuts.extend(_edge_fractions(a, b, c, d))
        cuts = sorted(set(cuts))
        for start, end in zip(cuts, cuts[1:]):
            t = (start + end) / 2
            point = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            if _locate(point, parent, bounds) == 'outside':
                return False
    return True


def _id(value):
    # Model PKs and IDs serialized by JSON both occur in snapshot consumers.
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    return str(value) if str(value).strip() else None


def _sort_zone(zone):
    return (LEVELS.index(zone['level']) if zone['level'] in LEVELS else -1,
            str(zone['id']))


def assess_location(row, zones):
    """Return status, selected_zone_id, matching_zone_ids and reason evidence.

    ``matching_zone_ids`` contains valid microzone rings which contain or touch
    the coordinate, also for approximate coordinates (reference only). District
    and broader polygons cannot become a selected microzone. Unbounded corrupt
    microzones block exact assignment conservatively; bounded corrupt rings only
    block points in their extent. Inactive zones are ignored.

    Top-level ``zona`` may be a standalone legacy root. More specific nodes need
    their immediate parent. Existing parent links must all resolve, be active,
    follow the model's level order and have geometrically coherent nesting.
    Administrative ancestors may omit geometry, as the current model permits.
    """
    evidence = []

    def note(code, message, zone_ids=None):
        item = {'code': code, 'message': message}
        if zone_ids is not None:
            item['zone_ids'] = list(zone_ids)
        evidence.append(item)

    def result(status, matching=(), selected=None):
        return {'status': status, 'selected_zone_id': selected,
                'matching_zone_ids': [zone['id'] for zone in matching],
                'evidence': evidence, 'rule_version': SPATIAL_RULE_VERSION}

    point = _point((row.get('latitud'), row.get('longitud')))
    if point is None:
        note('location.missing_or_invalid', 'Coordenadas ausentes, no finitas o fuera de rango; no se asigna microzona.')
        return result('missing')
    exact = row.get('precision_ubicacion') == 'exacta'
    note('location.declared_exact' if exact else 'location.reference_only',
         'Exacta declarada por la fuente; no equivale a ubicación catastral verificada.' if exact
         else 'Coordenadas aproximadas o sin precisión exacta declarada: solo referencia, sin asignación de microzona.')
    note('location.coordinate_order', 'Geometrías evaluadas como [latitud, longitud]; tolerancia numérica de 1e-9 grados.')
    if row.get('distrito'):
        note('location.district_not_microzone', 'El distrito declarado no se utiliza como microzona ni corrige las coordenadas.')

    compiled, by_id, duplicates = [], {}, set()
    invalid = []
    for snapshot in zones:
        if not isinstance(snapshot, Mapping):
            invalid.append((None, 'invalid_zone_snapshot'))
            continue
        if snapshot.get('activo', True) is False or snapshot.get('activo') == 0:
            continue
        key = _id(snapshot.get('id'))
        level = snapshot.get('nivel')
        ring, bounds, error = _geometry(snapshot.get('coordenadas'))
        zone = {'id': snapshot.get('id'), 'key': key, 'level': level,
                'parent': _id(snapshot.get('parent_id')), 'ring': ring,
                'bounds': bounds, 'error': error}
        if key is None:
            invalid.append((zone['id'], 'missing_zone_id'))
            continue
        if key in by_id:
            duplicates.add(key)
        by_id[key] = zone
        compiled.append(zone)
        if level not in LEVELS or level in MICRO_LEVELS and error:
            if bounds is None or _in_bounds(point, bounds):
                invalid.append((zone['id'], error or 'unknown_zone_level'))
    compiled.sort(key=_sort_zone)
    matching, boundary = [], []
    for zone in compiled:
        if zone['level'] not in MICRO_LEVELS or zone['error']:
            continue
        location = _locate(point, zone['ring'], zone['bounds'])
        if location != 'outside':
            matching.append(zone)
        if location == 'boundary':
            boundary.append(zone)
    if matching:
        note('zone.geometric_matches', 'Polígonos de microzona que contienen o tocan las coordenadas.', [z['id'] for z in matching])
    if boundary:
        note('zone.boundary', 'Punto sobre o numéricamente próximo a una frontera; no se decide un lado.', [z['id'] for z in boundary])
    for zone_id, error in invalid:
        note('zone.invalid_geometry', 'Geometría no utilizable: ' + error + '.', [zone_id] if zone_id is not None else [])
    if duplicates:
        note('zone.duplicate_id', 'El catálogo repite identificadores; no se puede resolver la jerarquía.', sorted(duplicates))
    if not exact:
        return result('approximate_reference', matching)
    if invalid or duplicates:
        return result('invalid_zone', matching)
    if boundary:
        return result('ambiguous', matching)
    if not matching:
        note('zone.no_microzone', 'Ningún polígono activo de zona, subzona o cuadrante contiene el punto.')
        return result('exact_unzoned')
    if len({zone['level'] for zone in matching}) != len(matching):
        note('zone.same_level_overlap', 'Coinciden polígonos distintos del mismo nivel; requiere revisión sin usar precios.', [z['id'] for z in matching])
        return result('ambiguous', matching)

    selected = matching[-1]
    current = selected
    chain, seen = [], set()
    while current is not None:
        if current['key'] in seen:
            note('zone.hierarchy_cycle', 'La jerarquía contiene un ciclo.', [current['id']])
            return result('ambiguous', matching)
        seen.add(current['key'])
        chain.append(current)
        parent_key = current['parent']
        if parent_key is None:
            if current['level'] in ('subzona', 'cuadrante'):
                note('zone.parent_missing', 'La microzona específica no tiene el padre requerido.', [current['id']])
                return result('ambiguous', matching)
            break
        parent = by_id.get(parent_key)
        if parent is None:
            note('zone.parent_unavailable', 'El padre referenciado falta en el catálogo activo.', [current['id']])
            return result('ambiguous', matching)
        if parent['level'] not in LEVELS or LEVELS.index(parent['level']) != LEVELS.index(current['level']) - 1:
            note('zone.parent_level', 'La cadena de padres no sigue los niveles definidos del proyecto.', [current['id'], parent['id']])
            return result('ambiguous', matching)
        current = parent
    if any(zone['key'] not in seen for zone in matching):
        note('zone.unrelated_overlap', 'Los polígonos coincidentes no pertenecen a una misma cadena de padres.', [z['id'] for z in matching])
        return result('ambiguous', matching)

    previous_ring = selected['ring']
    previous_id = selected['id']
    for ancestor in chain[1:]:
        if ancestor['error']:
            if ancestor['level'] not in MICRO_LEVELS and ancestor['error'] in ('missing_polygon', 'too_few_vertices') and not ancestor['ring']:
                note('zone.administrative_geometry_absent', 'Ancestro administrativo sin polígono: no se toma como microzona.', [ancestor['id']])
                continue
            note('zone.invalid_ancestor', 'La geometría de un ancestro es inválida: ' + ancestor['error'] + '.', [ancestor['id']])
            return result('invalid_zone', matching)
        if not _nested(previous_ring, ancestor['ring']):
            note('zone.inconsistent_nesting', 'El polígono hijo no está completamente contenido en el del ancestro.', [previous_id, ancestor['id']])
            return result('ambiguous', matching)
        ancestor_location = _locate(point, ancestor['ring'], ancestor['bounds'])
        if ancestor_location == 'boundary':
            note('zone.ancestor_boundary', 'El punto cae en una frontera de su jerarquía.', [ancestor['id']])
            return result('ambiguous', matching)
        previous_ring, previous_id = ancestor['ring'], ancestor['id']
    note('zone.selected_by_geometry', 'Se selecciona el polígono más específico de una jerarquía geométricamente coherente; pendiente de certificación.', [selected['id']])
    return result('exact_zone', matching, selected['id'])
