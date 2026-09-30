"""Deterministic offer-price experiments. No executable model deserialization."""
import hashlib
import math
from collections import defaultdict

TYPES = ('Casa', 'Terreno', 'Departamento', 'Oficina')
VERSION = 'offer-pricing-v1'


def finite(value, default=None):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError, OverflowError):
        return default


def features(row):
    data = row['features']
    return {
        'land': finite(data.get('area_terreno'), 0),
        'built': finite(data.get('area_construida'), 0),
        'age': finite(data.get('antiguedad_anios')),
        'lat': finite(data.get('latitud')),
        'lng': finite(data.get('longitud')),
        'zone': str(data.get('zone_id') or ''),
    }


def _distance(a, b):
    if None in (a['lat'], a['lng'], b['lat'], b['lng']):
        return 100000.0
    lat = math.radians((a['lat'] + b['lat']) / 2)
    x = (a['lng'] - b['lng']) * math.cos(lat) * 111320
    y = (a['lat'] - b['lat']) * 110540
    return math.hypot(x, y)


def _ratio(a, b):
    if not a or not b:
        return 1.0
    return max(0.5, min(2.0, a / b))


def _analog_price(kind, target, source, price):
    if kind == 'Casa':
        return price * (0.7 * _ratio(target['land'], source['land']) +
                        0.3 * _ratio(target['built'], source['built']))
    field = 'land' if kind == 'Terreno' else 'built'
    return price * _ratio(target[field], source[field])


def fit_knn(rows, kind):
    return {'algorithm': 'local_knn', 'version': VERSION, 'kind': kind,
            'examples': [{'features': features(row), 'price': row['price'],
                          'id': row['id'], 'group': row['group']} for row in rows]}


def predict_knn(model, target):
    kind = model['kind']
    close = []
    for row in model['examples']:
        source = row['features']
        meters = _distance(target, source)
        area = abs(math.log(max(target['land'], 1) / max(source['land'], 1))) if kind in ('Casa', 'Terreno') else 0
        if kind != 'Terreno':
            area += abs(math.log(max(target['built'], 1) / max(source['built'], 1)))
        age = abs(target['age'] - source['age']) / 40 if target['age'] is not None and source['age'] is not None else 0.15
        score = 0.65 * area + 0.25 * min(meters / 1500, 3) + 0.1 * age
        if target['zone'] and source['zone'] == target['zone']:
            score *= 0.75
        close.append((score, row, meters))
    close.sort(key=lambda item: (item[0], item[1]['id']))
    selected = close[:min(5, len(close))]
    if not selected:
        raise ValueError('No hay ejemplos de entrenamiento para este tipo.')
    weights = [1 / max(0.2, score) ** 2 for score, _, _ in selected]
    price = sum(weight * _analog_price(kind, target, row['features'], row['price'])
                for weight, (_, row, _) in zip(weights, selected)) / sum(weights)
    return price, [{'id': row['id'], 'distance_m': round(meters), 'similarity': round(100 / (1 + score), 1)}
                   for score, row, meters in selected]


def _base_vector(data, kind, zones):
    age = data['age']
    values = [1.0]
    if kind in ('Casa', 'Terreno'):
        values.append(math.log1p(data['land']))
    if kind != 'Terreno':
        values.append(math.log1p(data['built']))
        values.extend([min(age or 0, 20) / 20, max(0, min((age or 0) - 20, 30)) / 30,
                       1.0 if age is None else 0.0])
    values.extend([(data['lat'] or 0) + 16.4, (data['lng'] or 0) + 71.5])
    values.extend(1.0 if data['zone'] == zone else 0.0 for zone in zones)
    return values


def _solve(matrix, vector):
    n = len(vector)
    data = [list(matrix[i]) + [vector[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(data[row][col]))
        if abs(data[pivot][col]) < 1e-10:
            raise ValueError('El sistema de ajuste es singular.')
        data[col], data[pivot] = data[pivot], data[col]
        factor = data[col][col]
        for k in range(col, n + 1):
            data[col][k] /= factor
        for row in range(n):
            if row == col:
                continue
            factor = data[row][col]
            for k in range(col, n + 1):
                data[row][k] -= factor * data[col][k]
    return [data[i][n] for i in range(n)]


def fit_ridge(rows, kind):
    counts = defaultdict(int)
    for row in rows:
        counts[features(row)['zone']] += 1
    zones = [zone for zone, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
             if zone and count >= 4][:12]
    raw = [_base_vector(features(row), kind, zones) for row in rows]
    ncol = len(raw[0])
    means = [sum(row[j] for row in raw) / len(raw) for j in range(ncol)]
    scales = [max(0.2, (sum((row[j] - means[j]) ** 2 for row in raw) / len(raw)) ** 0.5)
              for j in range(ncol)]
    means[0], scales[0] = 0.0, 1.0
    x = [[(v - means[j]) / scales[j] for j, v in enumerate(row)] for row in raw]
    y = [math.log(row['price']) for row in rows]
    matrix = [[sum(row[i] * row[j] for row in x) for j in range(ncol)] for i in range(ncol)]
    rhs = [sum(row[j] * target for row, target in zip(x, y)) for j in range(ncol)]
    for j in range(1, ncol):
        matrix[j][j] += 5.0
    coefficients = _solve(matrix, rhs)
    return {'algorithm': 'hedonic_ridge', 'version': VERSION, 'kind': kind,
            'zones': zones, 'means': means, 'scales': scales, 'coefficients': coefficients}


def predict_ridge(model, target):
    raw = _base_vector(target, model['kind'], model['zones'])
    value = sum(coef * (v - model['means'][j]) / model['scales'][j]
                for j, (coef, v) in enumerate(zip(model['coefficients'], raw)))
    return math.exp(min(20, max(0, value))), []


def predict(model, row):
    target = features(row)
    if model['algorithm'] == 'local_knn':
        return predict_knn(model, target)
    if model['algorithm'] == 'hedonic_ridge':
        return predict_ridge(model, target)
    raise ValueError('Algoritmo desconocido.')


def split(rows):
    """Disjoint identity, time and whole-zone holdouts. Empty tests stay explicit."""
    groups = defaultdict(list)
    for row in rows:
        groups[row['group']].append(row)
    units = list(groups.values())
    units.sort(key=lambda unit: (max(str(row['seen'] or '') for row in unit), unit[0]['group']))
    unique_days = {str(row['seen'] or '')[:10] for row in rows if row['seen']}
    temporal = []
    if len(unique_days) >= 3 and len(units) >= 25:
        count = max(5, math.ceil(len(units) * 0.2))
        temporal, units = units[-count:], units[:-count]
    zone_groups = defaultdict(list)
    for unit in units:
        zone_groups[features(unit[0])['zone']].append(unit)
    spatial = []
    eligible = [(zone, parts) for zone, parts in zone_groups.items()
                if zone and 5 <= len(parts) <= max(5, len(units) * 0.3)]
    if len(zone_groups) >= 3 and eligible:
        zone, spatial = min(eligible, key=lambda item: hashlib.sha256(item[0].encode()).hexdigest())
        units = [unit for unit in units if features(unit[0])['zone'] != zone]
    flatten = lambda parts: [row for unit in parts for row in unit]
    return {'train': flatten(units), 'temporal': flatten(temporal), 'spatial': flatten(spatial)}


def metrics(cases):
    if not cases:
        return {'count': 0, 'available': False}
    errors = [case['predicted'] - case['price'] for case in cases]
    pct = [abs(error) / case['price'] for error, case in zip(errors, cases)]
    ordered = sorted(pct)
    return {'count': len(cases), 'available': True,
            'mae_usd': round(sum(abs(x) for x in errors) / len(errors), 2),
            'mape_pct': round(100 * sum(pct) / len(pct), 2),
            'bias_pct': round(100 * sum(error / case['price'] for error, case in zip(errors, cases)) / len(errors), 2),
            'within_10_pct': round(100 * sum(x <= .10 for x in pct) / len(pct), 1),
            'within_15_pct': round(100 * sum(x <= .15 for x in pct) / len(pct), 1),
            'within_20_pct': round(100 * sum(x <= .20 for x in pct) / len(pct), 1),
            'p80_error_pct': round(100 * ordered[min(len(ordered)-1, math.ceil(.8*len(ordered))-1)], 2)}


def evaluate(model, rows, role):
    cases = []
    for row in rows:
        estimated, evidence = predict(model, row)
        cases.append({'id': row['id'], 'role': role, 'price': row['price'],
                      'predicted': round(estimated, 2), 'portal': row['features'].get('fuente'),
                      'zone': features(row)['zone'], 'evidence': evidence})
    return cases, metrics(cases)
