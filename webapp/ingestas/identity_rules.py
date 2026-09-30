"""Pure, bounded suggestions of property identity; never merge or exclude rows.

``score`` is an ordinal review priority, NOT a probability. An exact source ID or
known portal detail URL identifies an advertisement, not a cadastral property.
All returned edges remain ``possible`` and require human review. Consumers must
not treat transitive components as confirmed identity or suppress their members.

Recall is intentionally limited: fuzzy suggestions require declared-exact Peru
coordinates, the same numbered address, price/required areas, distinctive prose,
and an explicit unit for buildings. Approximate locations can only match through
an advertisement identifier. Source IDs and URLs are compared without network I/O.

No global all-pairs comparison: direct identities use a sparse star; fuzzy blocks
use address/type/operation and neighboring 100 m grid cells with at most 16 nearby
price entries per cell. Dense blocks can omit valid edges. Complexity is bounded
by O(N log N + N * 9 * 16), excluding input text length, and is order independent.
"""
from bisect import bisect_left
from collections import Counter, defaultdict
import math
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


RULE_VERSION = 'property-identity-v1'
MAX_NEIGHBORS_PER_BLOCK = 16
MAX_DISTANCE_METRES = 60
_CELL_METRES = 100
_METRES_PER_DEGREE = 111195
_LON_SCALE = math.cos(math.radians(12))
_KINDS = {'casa', 'terreno', 'departamento', 'oficina', 'local', 'hotel'}
_BUILDINGS = {'departamento', 'oficina', 'local', 'hotel'}
_MISSING = {'', 'none', 'null', 'nan', 'n/a', 'na', 'sin dato', 'sin datos',
            'sin id', 'no especificado', 'desconocido', '0', '-'}
_TRACKING = {'fbclid', 'gclid', 'dclid', 'msclkid', 'utm_source', 'utm_medium',
             'utm_campaign', 'utm_term', 'utm_content', 'utm_id'}
_DETAIL_PATHS = {
    'adondevivir.com': r'^/propiedades/(?:clasificado/)?[^/]+/?$',
    'urbania.pe': r'^/(?:inmueble/(?:clasificado/)?|item/|propiedades/(?:clasificado/)?)[^/]+/?$',
    'properati.com.pe': r'^/detalle/[^/]+(?:/[^/]+)*/?$',
    'remax.pe': r'^/web/(?:search/)?(?:property|propiedad|inmueble)/[^/]+/?$',
    'facebook.com': r'^/marketplace/item/\d+/?$',
}
_STOPWORDS = set('''a al algo ante bajo con contra de del desde donde durante e el
ella en entre es esta este esto estos estas ha hacia hasta la las lo los mas muy
o para por que se sin sobre su sus te tu tus un una unos unas y ya casa casas
departamento departamentos inmueble inmuebles propiedad propiedades terreno
terrenos oficina local venta vende vendo alquiler alquila precio dolares usd soles
area construida terreno m2 metros cuadrados hermosa hermoso hermoso excelente
oportunidad ideal inversion ubicacion ubicado ubicada zona exclusiva exclusivo
amplia amplio iluminado iluminada cerca centros comerciales colegios universidades
bancos parques transporte publico tranquilidad seguridad comodidad confort lujo
moderno moderna acabados finos primer calidad vista lindo linda espectacular
contacto contactanos llamanos llamar llamadas informes informacion agenda visita
asesor agente inmobiliaria inmobiliario remax urbania adondevivir properati'''.split())
_UNIT = re.compile(r'\b(?:dpto|depto|departamento|oficina|interior|int|unidad|local)'
                   r'\s*(?:n(?:ro|umero)?\s*)?([a-z]?\d+[a-z]?)\b'
                   r'(?!\s*(?:m2|m²|metros|dormitorios?|dorm|ambientes?|habitaciones?|'
                   r'habitacion|recamaras?|rooms?|bedrooms?|banos?|bathrooms?|pisos?|niveles?)\b)')
_NUMBERED_ADDRESS = re.compile(r'\b\d{1,5}[a-z]?\b')
_APPROX_ADDRESS = re.compile(r'\b(?:cuadra|altura|referencia|aproximad\w*|entre)\b|\bs\s*/\s*n\b')


def _plain(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').lower())
                   if not unicodedata.combining(c))


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _id_sort(value):
    return (0, value) if isinstance(value, int) else (1, str(value))


def _source_key(row):
    source = _plain(row.get('fuente')).strip()
    origin = str(row.get('id_origen') if row.get('id_origen') is not None else '').strip()
    if source in _MISSING or _plain(origin) in _MISSING:
        return None
    # IDs may be case-sensitive; never lowercase or coerce their contents.
    return source, origin


def canonical_detail_url(value):
    """Conservative known-portal detail URL; unknown query parameters stay intact.

    No redirects are fetched. No arbitrary domain aliases, path case changes,
    removal of identifiers from queries, or scheme upgrades are inferred.
    """
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > 2048 or '\\' in value or any(ord(c) < 33 for c in value):
        return None
    try:
        parts = urlsplit(value)
        host = (parts.hostname or '').lower()
        host = host[4:] if host.startswith('www.') else host
        if (parts.scheme != 'https' or host not in _DETAIL_PATHS or parts.username
                or parts.password or parts.port not in (None, 443)):
            return None
        if not re.fullmatch(_DETAIL_PATHS[host], parts.path):
            return None
        # Do not collapse routing fragments or malformed/ambiguous paths.
        if parts.fragment.startswith(('/', '!')) or '/./' in parts.path or '/../' in parts.path:
            return None
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True, errors='strict')
                 if k.lower() not in _TRACKING]
        # Reordering repeated keys can alter application semantics.
        if len({key for key, _ in query}) == len(query):
            query.sort()
        return urlunsplit(('https', host, parts.path.rstrip('/'), urlencode(query), ''))
    except (ValueError, UnicodeError):
        return None


def _address(value):
    text = _plain(value).strip()
    if _APPROX_ADDRESS.search(text):
        return ''
    text = re.sub(r'\bavenida\b|\bav\b', 'av', text)
    text = re.sub(r'\bjiron\b|\bjr\b', 'jr', text)
    text = re.sub(r'\b(?:dpto|depto|departamento)\b', 'unidad', text)
    text = ' '.join(re.findall(r'[a-z0-9]+', text))
    # A unit number cannot stand in for a missing street/building number.
    street = _UNIT.sub('', text)
    numbering = re.sub(r'\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|'
                       r'agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b', '', street)
    return text if _NUMBERED_ADDRESS.search(numbering) and len(street.split()) >= 3 else ''


def _unit(row):
    # Multiple different unit mentions are ambiguous, including agency portfolios.
    text = _plain(' '.join(str(row.get(k) or '') for k in ('direccion_texto', 'titulo', 'descripcion')))
    text = re.sub(r'[.#º°:]+', ' ', text)
    matches = set(_UNIT.findall(text))
    return next(iter(matches)) if len(matches) == 1 else None


def _tokens(row):
    # Cap per-record work; omit agency/contact sentences and common marketing terms.
    text = _plain(row.get('descripcion'))[:6000]
    sentences = re.split(r'[.!?\n;]+', text)
    text = ' '.join(s for s in sentences if not re.search(
        r'\b(?:contact|llamanos|whatsapp|reserv|agend|comision|asesor|inmobiliaria)\w*', s))
    return {t for t in re.findall(r'\b[a-z][a-z0-9]{2,}\b', text) if t not in _STOPWORDS}


def _coordinates(row):
    lat, lon = _number(row.get('latitud')), _number(row.get('longitud'))
    if lat is None or lon is None or not (-19 <= lat <= 0 and -82 <= lon <= -68):
        return None
    if _plain(row.get('precision_ubicacion')).strip() != 'exacta':
        return None
    return lat, lon


def _prepare(row, record_id):
    return dict(id=record_id, source=_source_key(row), url=canonical_detail_url(row.get('url')),
                kind=_plain(row.get('tipo_inmueble')).strip(),
                operation=_plain(row.get('tipo_operacion')).strip(),
                price=_number(row.get('precio_usd')),
                land=_number(row.get('area_terreno')), built=_number(row.get('area_construida')),
                coords=_coordinates(row), address=_address(row.get('direccion_texto')),
                unit=_unit(row), tokens=_tokens(row))


def _block(row):
    if (row['kind'] not in _KINDS or row['operation'] not in {'venta', 'alquiler'}
            or not row['coords'] or not row['address'] or not row['price'] or row['price'] <= 0):
        return None
    lat, lon = row['coords']
    return (row['kind'], row['operation'], row['address'],
            math.floor(lat * _METRES_PER_DEGREE / _CELL_METRES),
            math.floor(lon * _METRES_PER_DEGREE * _LON_SCALE / _CELL_METRES))


def _candidate_pairs(rows):
    """Yield bounded, deterministic edges; caller deduplicates across blocks."""
    for field in ('source', 'url'):
        groups = defaultdict(list)
        for index, row in enumerate(rows):
            if row[field]:
                groups[row[field]].append(index)
        for group in groups.values():
            for index in group[1:]:
                yield group[0], index
    blocks = defaultdict(list)
    for index, row in enumerate(rows):
        key = _block(row)
        if key:
            blocks[key].append((row['price'], index))
    for entries in blocks.values():
        entries.sort()
    for index, row in enumerate(rows):
        key = _block(row)
        if not key:
            continue
        kind, operation, address, y, x = key
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                entries = blocks.get((kind, operation, address, y + dy, x + dx), ())
                centre = bisect_left(entries, (row['price'], index))
                start = max(0, centre - MAX_NEIGHBORS_PER_BLOCK // 2)
                for _, other in entries[start:start + MAX_NEIGHBORS_PER_BLOCK]:
                    if index != other:
                        yield min(index, other), max(index, other)


def _near(a, b, relative, absolute=0):
    return (a is not None and b is not None and a > 0 and b > 0
            and abs(a - b) <= max(absolute, max(a, b) * relative))


def _distance(a, b):
    lat_a, lon_a = map(math.radians, a)
    lat_b, lon_b = map(math.radians, b)
    value = math.sin((lat_b - lat_a) / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin((lon_b - lon_a) / 2) ** 2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(value)))


def _compare(left, right):
    evidence = []
    if left['source'] and left['source'] == right['source']:
        evidence.append(dict(code='identity.same_source_id', field='id_origen',
                             message='Mismo ID de anuncio dentro de la misma fuente.'))
    if left['url'] and left['url'] == right['url']:
        evidence.append(dict(code='identity.same_detail_url', field='url',
                             message='Misma URL canónica de ficha de un portal conocido.'))
    if evidence:
        score = 99 if len(evidence) == 2 else 98 if evidence[0]['code'].endswith('source_id') else 95
        for field in ('kind', 'operation', 'unit'):
            if left[field] and right[field] and left[field] != right[field]:
                evidence.append(dict(code='identity.conflict', field=field,
                                     message='El identificador coincide pero este dato difiere; revisar.',
                                     left=left[field], right=right[field]))
        return score, evidence
    if (left['kind'] != right['kind'] or left['operation'] != right['operation']
            or not left['coords'] or not right['coords'] or not left['address']
            or left['address'] != right['address']):
        return None
    if left['unit'] != right['unit'] or (left['kind'] in _BUILDINGS and not left['unit']):
        return None
    distance = _distance(left['coords'], right['coords'])
    if distance > MAX_DISTANCE_METRES or not _near(left['price'], right['price'], .02):
        return None
    required = ('land', 'built') if left['kind'] == 'casa' else ('land',) if left['kind'] == 'terreno' else ('built',)
    if not all(_near(left[field], right[field], .01, .5) for field in required):
        return None
    # Optional areas can contradict identity even when required areas agree.
    if any(left[field] and right[field] and not _near(left[field], right[field], .05, 1)
           for field in ('land', 'built')):
        return None
    shared = left['tokens'] & right['tokens']
    union = left['tokens'] | right['tokens']
    similarity = len(shared) / len(union) if union else 0
    if len(shared) < 12 or similarity < .8:
        return None
    evidence.extend([
        dict(code='property.same_kind_operation', message='Coinciden tipo y operación.'),
        dict(code='address.same_numbered', field='direccion_texto', message='Coincide la dirección con numeración.'),
        dict(code='location.declared_exact_nearby', field='latitud', distance_metres=round(distance, 1),
             message='Ambas ubicaciones se declaran exactas; cercanía solo como apoyo, no prueba de identidad.'),
        dict(code='price.close', field='precio_usd', left=left['price'], right=right['price'],
             message='Precios positivos con diferencia máxima del 2%.'),
        dict(code='area.close', fields=list(required),
             message='Superficies requeridas coincidentes dentro del 1% o 0,5 m².'),
        dict(code='text.distinctive_overlap', field='descripcion', shared_terms=len(shared),
             similarity=round(similarity, 3), message='Coincide prosa descriptiva tras filtrar términos genéricos.')])
    if left['unit']:
        evidence.append(dict(code='unit.same_explicit', field='direccion_texto', unit=left['unit'],
                             message='Coincide la unidad explícita; pendiente de verificación.'))
    return 85 if left['unit'] else 80, evidence


def propose_pairs(rows):
    """Return deterministic, review-only edges without changing any input row.

    Rows need a unique int/string ``pk`` (or ``id``). Missing/invalid IDs and all
    occurrences of repeated IDs are ignored: ambiguous versions must be resolved
    by the caller. Descriptions recurring in >10% of 40+ rows lose those recurring
    terms to reduce agency/project boilerplate. Nothing is fetched, trained,
    persisted, joined, deactivated or deleted by this function.
    """
    keyed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        record_id = row.get('pk') if row.get('pk') is not None else row.get('id')
        if (isinstance(record_id, bool) or not isinstance(record_id, (int, str))
                or (isinstance(record_id, str) and not record_id.strip())):
            continue
        keyed.append((record_id, row))
    counts = Counter(record_id for record_id, _ in keyed)
    prepared = [_prepare(row, record_id) for record_id, row in keyed if counts[record_id] == 1]
    prepared.sort(key=lambda row: _id_sort(row['id']))
    if len(prepared) >= 40:
        frequencies = Counter(token for row in prepared for token in row['tokens'])
        frequent = {token for token, count in frequencies.items() if count > max(4, len(prepared) * .1)}
        for row in prepared:
            row['tokens'] -= frequent
    results, seen = [], set()
    for left_index, right_index in _candidate_pairs(prepared):
        if (left_index, right_index) in seen:
            continue
        seen.add((left_index, right_index))
        left, right = prepared[left_index], prepared[right_index]
        match = _compare(left, right)
        if match:
            score, evidence = match
            results.append(dict(left_id=left['id'], right_id=right['id'], evidence=evidence,
                                score=score, status='possible'))
    results.sort(key=lambda pair: (_id_sort(pair['left_id']), _id_sort(pair['right_id'])))
    return results
