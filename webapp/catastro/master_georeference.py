"""Control-point calibration proposals. A small residual never certifies a map."""
import hashlib
import math
import re

from .master_store import encoded


def page_info(body, page):
    import fitz
    if type(page) is not int or page < 1:
        raise ValueError('Indica una página válida.')
    with fitz.open(stream=body, filetype='pdf') as document:
        if page > len(document):
            raise ValueError('Página no disponible.')
        sheet = document[page - 1]
        return {'page': page, 'width': sheet.rect.width, 'height': sheet.rect.height,
                'rotation': sheet.rotation, 'coordinate_space': 'rotated_page_points_top_left',
                'original_sha256': hashlib.sha256(body).hexdigest()}


def _number(value, label):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError('Número no válido: ' + label)
    return float(value)


def calibrate(body, request):
    """Fit in projected metres, reserve checkpoints and return a pending report."""
    import numpy as np
    from pyproj import CRS, Transformer
    from pyproj.exceptions import CRSError, ProjError
    from shapely.geometry import MultiPoint

    if not isinstance(request, dict):
        raise ValueError('Propuesta no válida.')
    page = page_info(body, request.get('page'))
    code = request.get('target_crs')
    if not isinstance(code, str) or not re.fullmatch(r'EPSG:[0-9]{4,6}', code):
        raise ValueError('Indica el EPSG de las coordenadas de control.')
    try:
        crs = CRS.from_user_input(code)
        if (not crs.is_projected or len(crs.axis_info) != 2
                or any(abs(axis.unit_conversion_factor - 1.) > 1e-12 for axis in crs.axis_info)):
            raise ValueError('Los controles requieren un sistema proyectado en metros, con ejes Este y Norte.')
        if [axis.direction for axis in crs.axis_info] != ['east', 'north']:
            raise ValueError('Selecciona un EPSG con orden Este, Norte.')
        to_wgs84 = Transformer.from_crs(crs, 'EPSG:4326', always_xy=True, allow_ballpark=False)
    except (CRSError, ProjError):
        raise ValueError('No se pudo preparar la transformación del EPSG indicado.') from None
    tolerance = _number(request.get('tolerance_m'), 'tolerancia')
    if tolerance <= 0:
        raise ValueError('La tolerancia debe ser mayor que cero y definida para este trabajo.')
    rows = request.get('points')
    if not isinstance(rows, list) or not 6 <= len(rows) <= 100:
        raise ValueError('Incluye al menos cuatro puntos de ajuste y dos de comprobación; máximo 100.')
    points, seen_ids, seen_page, seen_ground = [], set(), set(), set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Punto no válido.')
        pid, role, evidence = row.get('id'), row.get('role'), row.get('evidence')
        if not isinstance(pid, str) or not pid.strip() or len(pid) > 100 or pid in seen_ids:
            raise ValueError('Cada punto necesita un identificador único.')
        if role not in ('fit', 'check'):
            raise ValueError('El punto debe ser de ajuste o comprobación independiente.')
        if not isinstance(evidence, str) or not evidence.strip() or len(evidence) > 2000:
            raise ValueError('Documenta la fuente y fecha de las coordenadas de cada punto.')
        xy = tuple(_number(row.get(key), key) for key in ('pdf_x', 'pdf_y'))
        ground = tuple(_number(row.get(key), key) for key in ('easting', 'northing'))
        if not (0 <= xy[0] <= page['width'] and 0 <= xy[1] <= page['height']):
            raise ValueError('Hay un punto fuera de la página del PDF.')
        if xy in seen_page or ground in seen_ground:
            raise ValueError('No reutilices un punto como ajuste y comprobación ni dupliques coordenadas.')
        try:
            lon, lat = to_wgs84.transform(*ground, errcheck=True)
        except ProjError:
            raise ValueError('Coordenadas de control fuera del sistema indicado.') from None
        area = crs.area_of_use
        if (not math.isfinite(lon + lat) or not -180 <= lon <= 180 or not -90 <= lat <= 90
                or (area and not (area.west <= lon <= area.east and area.south <= lat <= area.north))):
            raise ValueError('Un control queda fuera del área de uso del EPSG indicado. Revisa EPSG y ejes.')
        points.append({'id': pid, 'role': role, 'evidence': evidence.strip(),
                       'pdf_x': xy[0], 'pdf_y': xy[1], 'easting': ground[0], 'northing': ground[1]})
        seen_ids.add(pid); seen_page.add(xy); seen_ground.add(ground)
    fit = [row for row in points if row['role'] == 'fit']
    check = [row for row in points if row['role'] == 'check']
    if len(fit) < 4 or len(check) < 2:
        raise ValueError('Se requieren cuatro puntos de ajuste y dos de comprobación independiente.')
    xy = np.array([[row['pdf_x'], row['pdf_y']] for row in fit])
    ground = np.array([[row['easting'], row['northing']] for row in fit])
    center = xy.mean(axis=0)
    scale = float(np.max(np.ptp(xy, axis=0)))
    design = np.column_stack(((xy - center) / scale, np.ones(len(fit))))
    coefficients, _, rank, singular = np.linalg.lstsq(design, ground, rcond=None)
    condition = float(singular[0] / singular[-1]) if singular[-1] else math.inf
    # Numerical guard, not a cadastral precision standard.
    linear = coefficients[:2] / scale
    if rank != 3 or condition > 1e6 or np.linalg.cond(linear) > 1e6:
        raise ValueError('Los controles están alineados o la transformación es inestable. Distribúyelos por el plano.')
    offset = coefficients[2] - center @ linear
    hull = MultiPoint(xy.tolist()).convex_hull
    from shapely.geometry import Point
    residuals = []
    for row in points:
        position = np.array([row['pdf_x'], row['pdf_y']])
        predicted = position @ linear + offset
        delta = predicted - [row['easting'], row['northing']]
        residuals.append({'id': row['id'], 'role': row['role'], 'dx_m': float(delta[0]),
                          'dy_m': float(delta[1]), 'error_m': float(np.linalg.norm(delta)),
                          'outside_fit_hull': not hull.covers(Point(position))})
    stats = {}
    for role in ('fit', 'check'):
        errors = [row['error_m'] for row in residuals if row['role'] == role]
        stats[role] = {'count': len(errors), 'rmse_m': math.sqrt(sum(v*v for v in errors) / len(errors)),
                       'max_m': max(errors)}
    report = {'format': 'catastro-calibracion-afin-v1', 'status': 'pending',
              'method': 'affine_least_squares_with_held_out_checkpoints', 'page': page,
              'target_crs': code, 'target_crs_name': crs.name, 'tolerance_m': tolerance,
              'within_tolerance': all(item['max_m'] <= tolerance for item in stats.values()),
              'matrix': [[float(linear[0,0]), float(linear[1,0]), float(offset[0])],
                         [float(linear[0,1]), float(linear[1,1]), float(offset[1])]],
              'fit_hull_page': list(map(list, hull.exterior.coords)),
              'fit_hull_page_fraction': hull.area / (page['width'] * page['height']),
              'condition_number': condition, 'points': points, 'residuals': residuals, 'statistics': stats,
              'limitations': ['Los errores miden coincidencia con los controles aportados, no precisión absoluta.',
                             'Revisar calidad e independencia de controles, cobertura, datum y uniones entre láminas.',
                             'Fuera de la envolvente de ajuste existe extrapolación. No se certifican ni activan lotes.']}
    return report


def report_token(version_id, report):
    return hashlib.sha256(encoded({'version_id': version_id, 'report': report}).encode()).hexdigest()
