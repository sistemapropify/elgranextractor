"""Read-only catalogue of listings the ACM can choose before a target is supplied."""
from .components_engine import SOURCES, kind, number, positive, reason
from .listing_operation import resolve_operation
from .reference_fallback import reference_usable
from urllib.parse import urlsplit


def annotate_catalog(row):
    link = str(row.get('url') or '').strip()
    try:
        parts = urlsplit(link)
        row['acm_listing_url'] = link if parts.scheme in ('https', 'http') and parts.hostname and not parts.username and not parts.password else ''
    except ValueError:
        row['acm_listing_url'] = ''
    record = {
        'id': str(row['id']), 'source': row['fuente'], 'kind': kind(row.get('tipo_inmueble')),
        'title': row.get('titulo'), 'url': row.get('url'), 'operation': row.get('tipo_operacion'),
        '_operation_title': row.get('original_listing_title'),
        '_operation_title_lower': row.get('original_listing_title_lower'),
        'price': positive(row.get('precio_usd')) or
                 (positive(row.get('precio_soles')) / 3.44 if positive(row.get('precio_soles')) else None),
        'land': positive(row.get('area_terreno')), 'built': positive(row.get('area_construida')),
        'precision': row.get('precision_ubicacion'), 'state': row.get('estado_publicacion'),
        'review_excluded': bool(row.get('excluida')),
    }
    record['operation'], record['operation_status'] = resolve_operation(record)
    lat, lng = number(row.get('latitud')), number(row.get('longitud'))
    gates = []
    if record['source'] not in SOURCES: gates.append('Portal no habilitado en el ACM')
    if record['kind'] is None: gates.append('Tipo de propiedad no admitido en el ACM')
    if lat is None or lng is None or not -90 <= lat <= 90 or not -180 <= lng <= 180:
        gates.append('Sin coordenadas GPS válidas')
    if record['operation'] != 'Venta': gates.append('Operación de venta sin confirmar')
    # Own surfaces neutralize target-dependent size checks. Location, radius,
    # target age and duplicate selection are decided inside each actual ACM.
    params = {'property_type': record['kind'], 'land': record['land'] or 1,
              'built': record['built'] or 1, 'age': None}
    issues = list(dict.fromkeys(gates + reason(record, params)))
    primary = not issues
    area = 'land' if record['kind'] == 'Terreno' else 'built'
    secondary = not gates and reference_usable(record, area)
    row.update(acm_available=bool(primary or secondary), acm_primary=primary,
               acm_secondary=bool(secondary), acm_issues=issues,
               acm_status='principal' if primary else 'referencia' if secondary else 'fuera')
    return row


def propify_catalog_rows():
    """Use the exact available-listing loader already used by the ACM."""
    from .components_views import bounded_propify_rows
    result = []
    for source in bounded_propify_rows():
        result.append({
            'id': source['id'], 'fuente': 'propify', 'id_origen': source['code'],
            'titulo': source['title'], 'tipo_inmueble': source['kind'],
            'tipo_operacion': source['operation'], 'precio_usd': source['price'],
            'precio_soles': None, 'area_terreno': source['land'],
            'area_construida': source['built'], 'area_m2': None,
            'distrito': source['district'], 'latitud': source['lat'], 'longitud': source['lng'],
            'precision_ubicacion': source['precision'], 'estado_publicacion': source['state'],
            'url': source['url'], 'antiguedad_anios': source.get('age'),
            'excluida': False, 'correcta': False, 'motivo': '', 'ia_veredicto': None,
        })
    return result
