"""Read-only, explainable map alerts. Alerts never delete or exclude listings."""
from collections import Counter, defaultdict
import math
from statistics import quantiles


def positive(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and value > 0 else None
    except (TypeError, ValueError):
        return None


def annotate_map_quality(properties):
    groups = defaultdict(list)
    for row in properties:
        raw = row.pop('_quality_input', {})
        land = positive(raw.get('land', row.get('land_area_m2')))
        built = positive(raw.get('built', row.get('built_area_m2')))
        price = positive(raw.get('usd')) or positive(row.get('price'))
        if not positive(raw.get('usd')) and row.get('currency_symbol') != '$' and price:
            price /= 3.44
        kind = str(row.get('property_type') or '').strip().casefold()
        operation = str(row.get('operation_type') or '').strip().casefold()
        alerts = []

        def flag(code, category, message):
            alerts.append({'code': code, 'category': category, 'message': message})

        if not price:
            flag('price_missing', 'incomplete', 'Falta un precio positivo.')
        if kind in ('casa', 'house'):
            if not land:
                flag('land_missing', 'incomplete', 'Casa sin área de terreno explícita: solo referencia en el ACM por componentes.')
            if not built:
                flag('built_missing', 'incomplete', 'Casa sin área construida explícita: solo referencia en el ACM por componentes.')
            if land and land < 30:
                flag('small_house_land', 'review', f'Casa con terreno de {land:g} m² (menor de 30 m²): comprobar la superficie en el anuncio.')
        elif kind in ('terreno', 'land', 'lote'):
            if not land:
                flag('land_missing', 'incomplete', 'Terreno sin área de terreno explícita.')
            if built:
                flag('land_with_building', 'review', 'El terreno tiene construcción: no debe usarse como referencia de suelo vacío.')
        elif not built and not land:
            flag('area_missing', 'incomplete', 'Sin superficie explícita para comparar.')
        if raw.get('legacy_area'):
            flag('legacy_area', 'review', 'Superficie histórica sin clasificación explícita: revisar si corresponde a terreno o construcción.')
        if str(row.get('location_precision') or '').casefold() != 'exacta':
            flag('location_precision', 'review', 'Ubicación aproximada o desconocida: revisar antes de usar en una microzona.')
        district = str(row.get('district') or '').strip()
        if not district or district.casefold() == 'sin distrito':
            flag('district_missing', 'incomplete', 'Falta distrito.')
        try:
            lat, lng = float(row.get('lat')), float(row.get('lng'))
            located = math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180 and (lat != 0 or lng != 0)
        except (TypeError, ValueError):
            located = False
        if not located:
            flag('coordinates_missing', 'incomplete', 'Coordenadas incompletas o inválidas: no se puede ubicar en el mapa.')
        if row.get('quality_excluded'):
            flag('manually_excluded', 'excluded', 'Excluida del ACM por revisión: ' + str(row.get('quality_exclusion_reason') or 'Sin motivo registrado'))
        row['quality_alerts'] = alerts

        # Whole house price includes land and improvements: never compare its
        # price/built-area ratio to a fixed threshold or call it a soil value.
        surface = land if kind in ('terreno', 'land', 'lote') else built if kind in ('departamento', 'apartment') else None
        if operation == 'venta' and surface and price and not alerts and row.get('quality_stat_eligible', True):
            canonical_kind = 'Terreno' if kind in ('terreno', 'land', 'lote') else 'Departamento'
            groups[(district.casefold(), canonical_kind)].append((row, price / surface, surface))

    for (_, kind), items in groups.items():
        for row, ratio, area in items:
            # Comparable sizes only; avoid comparing large lots to tiny lots.
            peers = []
            seen = set()
            for other, unit, size in items:
                identity = str(other.get('url') or f"{other.get('source_key')}:{other['id']}").rstrip('/')
                if .5 <= size / area <= 2 and identity not in seen:
                    peers.append(unit)
                    seen.add(identity)
            if len(peers) < 8:
                continue
            q1, _, q3 = quantiles(peers, n=4, method='inclusive')
            iqr = q3 - q1
            low, high = max(0, q1 - 3 * iqr), q3 + 3 * iqr
            if iqr > 0 and (ratio < low or ratio > high):
                row['quality_alerts'].append({
                    'code': 'unit_price_outlier', 'category': 'outlier',
                    'message': f'Posible valor atípico: US$ {ratio:,.0f}/m² frente a {len(peers)} anuncios de {kind.lower()}, venta, mismo distrito y tamaño similar. Rango 3 IQR: US$ {low:,.0f}–{high:,.0f}/m². Requiere revisión; no confirma un error.',
                })

    for row in properties:
        categories = {a['category'] for a in row['quality_alerts']}
        row['quality_status'] = next((s for s in ('excluded', 'outlier', 'incomplete', 'review') if s in categories), 'clear')
    counts = Counter(r['quality_status'] for r in properties)
    return {'total': len(properties), 'with_alerts': len(properties) - counts['clear'],
            'outlier': counts['outlier'], 'incomplete': counts['incomplete'],
            'review': counts['review'], 'excluded': counts['excluded'], 'clear': counts['clear']}
