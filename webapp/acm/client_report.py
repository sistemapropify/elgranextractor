"""Shared client-facing content and images for PDF and editable Word reports."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from statistics import mean
import time
import re

PDM_PARAMETER_FIELDS = (
    ('densidad', 'Densidad'),
    ('lote_minimo', 'Lote mínimo'),
    ('frente_minimo', 'Frente mínimo'),
    ('altura', 'Altura'),
    ('coeficiente', 'Coeficiente'),
    ('area_libre', 'Área libre'),
    ('retiros', 'Retiros'),
    ('alineamiento', 'Alineamiento'),
    ('estacionamiento', 'Estacionamiento'),
)


def pdm_zone(params):
    """Resolve the PDM use zone and its normative parameter table."""
    try:
        from cuadrantizacion.zonificacion import clasificar_punto
        zone = clasificar_punto(params.get('lat'), params.get('lng'))
    except Exception:
        return None
    if not zone:
        return None
    parameters = zone.get('parametros') if isinstance(zone.get('parametros'), dict) else {}
    blocks = parameters.get('bloques')
    if not isinstance(blocks, list) or not blocks:
        ignored = {'bloques', 'usos_compatibles', 'notas'}
        blocks = [{key: value for key, value in parameters.items() if key not in ignored}]
    blocks = [block for block in blocks if isinstance(block, dict)]
    typologies = [str(block.get('tipologia') or 'Parámetros') for block in blocks]
    def display(value):
        return re.sub(r'(?<=\d)\.00\b', '', str(value))
    rows = []
    for key, label in PDM_PARAMETER_FIELDS:
        values = [block.get(key) for block in blocks]
        if any(value not in (None, '') for value in values):
            rows.append({'label': label,
                         'values': ['Sin informar' if value in (None, '') else display(value)
                                    for value in values]})
    return {
        'codigo': zone.get('codigo') or '',
        'nombre': zone.get('uso') or '',
        'categoria': zone.get('categoria') or '',
        'color': zone.get('color') or '',
        'property_type': params.get('property_type') or '',
        'confidence': zone.get('confianza') or '',
        'approximate': bool(zone.get('aproximado')),
        'distance_edge': zone.get('distancia_borde_m'),
        'typologies': typologies,
        'rows': rows,
        'compatible_uses': parameters.get('usos_compatibles') or '',
        'notes': parameters.get('notas') if isinstance(parameters.get('notas'), list) else [],
    }


def author_name(user):
    full = getattr(user, 'get_full_name', lambda: '')() if user else ''
    if not full and user:
        full = ' '.join(str(getattr(user, key, '') or '') for key in ('first_name', 'last_name'))
    return ' '.join(str(full or getattr(user, 'username', '') or 'Propify').split())


def prepare_report(params, records, result, excluded=(), generated_at=None, user=None, fetch_images=True):
    from . import components_pdf as media
    from .report_selection import report_records, report_values, report_unit_price
    peru = timezone(timedelta(hours=-5))
    generated_at = generated_at or datetime.now(peru)
    if generated_at.tzinfo:
        generated_at = generated_at.astimezone(peru)
    rows = report_records(params, records, excluded)
    if 'report_ids' not in params:
        rows = media._selection(rows, result, excluded)
    target_kind = 'Terreno' if result.get('valuation_mode') == 'land_only' else params.get('property_type', 'Casa')
    primary = [row for row in rows if row.get('kind') == target_kind]
    reference_mode = result.get('reference_mode', False)
    # The client sheet has one strip of five properties. Supporting land records
    # still participate in the valuation, but do not add another photo strip.
    rows = sorted(primary or rows, key=lambda row: row.get('distance') or 0)[:5]
    primary = rows
    groups = []
    if primary:
        groups.append(('REFERENCIAS EN VENTA' if reference_mode else 'COMPARABLES EN VENTA', primary))
    units = [(row, media._unit_price(row)) for row in primary or rows]
    units = [(row, unit) for row, unit in units if unit is not None]
    average = report_unit_price(params, result, mean(v for _, v in units) if units else None)
    deadline = time.monotonic() + 24
    permissions = params.get('_acm_permissions', {})
    photo_allowed = permissions.get('report_photos', False) and permissions.get('photos', True)
    photos = {}
    if fetch_images:
        def photo(row):
            return row['id'], media._property_photo(row.get('image'), deadline)
        with ThreadPoolExecutor(max_workers=4) as pool:
            if photo_allowed:
                photos = {key: image for key, image in pool.map(photo, rows) if image}
    center = (params['lat'], params['lng'])
    markers = [f'color:0x008f91|label:P|{center[0]},{center[1]}']
    for i, row in enumerate(rows):
        label = f'|label:{i+1}' if i < 9 else ''
        markers.append(f'color:0x475569{label}|{row["lat"]},{row["lng"]}')
    map_image = media._static_map(center, markers, media._maps_key(), size=(640, 360),
                                   zoom=15, fetch=fetch_images, deadline=deadline)
    croquis = not map_image
    if croquis:
        map_image = media._croquis(center, [(r['lat'], r['lng']) for r in rows], params['radius'])
    chart = media._bar_chart([str(rows.index(r)+1) for r, _ in units], [v for _, v in units], average) if units and average is not None else None
    address = media._clean(params.get('address'))
    if not address:
        address = media._zona_text(*center, media._maps_key(static=False), fetch_images)
    summary = ('Este cálculo usa las referencias más cercanas disponibles dentro del radio seleccionado, '
               'con precio y metraje válidos. Las diferencias de ubicación, antigüedad y disponibilidad '
               'deben revisarse al adoptar el valor.' if reference_mode else
               'La estimación considera las propiedades seleccionadas y sus características. '
               'Los importes corresponden a precios de oferta y pueden diferir del precio final de compraventa.')
    return dict(params=params, result=result, rows=rows, groups=groups, photos=photos,
                map=map_image, croquis=croquis, chart=chart, average=average,
                address=address, author=author_name(user), date=generated_at, summary=summary,
                values=report_values(params, result) if result.get('new') else None,
                notes=params.get('report_notes', ''), logo=media._logo_bytes(),
                pdm=pdm_zone(params))


def age(value):
    return 'Sin informar' if value is None else 'Estreno' if value == 0 else f'{value:g} años' if isinstance(value, (int, float)) else f'{value} años'


RESULT_LABELS = [('VALOR DE SALIDA AL MERCADO', 'market_entry'), ('VALOR COMERCIAL', 'commercial'),
                 ('VALOR DE REALIZACIÓN INMEDIATA', 'immediate')]
