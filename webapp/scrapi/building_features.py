"""Conservative, shared parking/elevator extraction. No network or database I/O."""
import re
import unicodedata
from copy import deepcopy

VERSION = 1
PARKING_TYPES = {
    'lineal_techada': 'Lineal techada',
    'lineal_no_techada': 'Lineal no techada',
    'paralela_techada': 'Paralela techada',
    'paralela_no_techada': 'Paralela no techada',
}
SUPPORTED = {'casa', 'departamento', 'apartamento', 'duplex', 'triplex', 'flat', 'oficina', 'consultorio'}
PARK = r'(?:cocheras?|estacionamientos?|garajes?|garages?|parking)'
LIFT = r'(?:ascensor(?:es)?|elevador(?:es)?|elevators?)'
NUMBERS = {'un': 1, 'una': 1, 'uno': 1, 'otra': 1, 'otro': 1, 'dos': 2, 'tres': 3,
           'cuatro': 4, 'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10}
NUM = r'(?:\d{1,3}|' + '|'.join(NUMBERS) + r')'
SOURCE_KEYS = {'cocheras', 'estacionamientos', 'garaje', 'garage', 'parking', 'ascensor',
               'ascensores', 'elevador', 'elevadores', 'elevator', 'caracteristicas',
               'caracteristicas extra', 'amenities', 'features', 'facilities',
               'descripcion', 'description', 'descripcion completa', '_detail features',
               '_detail description', 'servicios', 'equipamiento'}


def plain(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value)).lower()
                   if not unicodedata.combining(c))


def _integer(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 0 <= value <= 100:
        return value
    text = str(value).strip()
    if text in NUMBERS:
        return NUMBERS[text]
    return int(text) if re.fullmatch(r'\d{1,3}', text) and int(text) <= 100 else None


def _sources(raw, description, amenities=None):
    seen = set()
    def values(value):
        if isinstance(value, dict):
            for k, v in list(value.items())[:150]:
                if v is not None:
                    yield f'{k}: {v}'
        elif isinstance(value, (list, tuple)):
            for part in value[:150]:
                yield from values(part)
        elif isinstance(value, (str, int, float, bool)):
            yield str(value)
    for key, value in list(raw.items()) + [('descripcion', description), ('amenities', amenities)]:
        name = plain(key).replace('_', ' ').strip()
        if name not in {k.replace('_', ' ').strip() for k in SOURCE_KEYS}:
            continue
        for text in values(value):
            if not text.strip():
                continue
            if re.fullmatch(r'[-—–\s]+', text) or plain(text).strip() in ('sin informacion', 'no informado', 'no especificado', 'n/a', 'null'):
                continue
            # A named field's value may just be "2 Paralelo Techado" or "No".
            if re.fullmatch(PARK + '|' + LIFT, name):
                if isinstance(value, bool):
                    text = name + (': si' if value else ': no')
                else:
                    text = name + ': ' + text
            if text not in seen:
                seen.add(text)
                yield str(key), text[:30000]


def _claims(field, original):
    text = plain(original)
    # Recommendations and the rest of a page are deliberately never inputs.
    for sentence in re.split(r'[\n\r|;•]+|(?<=[.!?])\s+', text):
        if not re.search(r'\b(?:' + PARK + '|' + LIFT + r')\b', sentence):
            continue
        yield field, sentence.strip()


def _negative(text, noun):
    return bool(re.search(r'\b(?:sin|no (?:tiene|hay|incluye)|no cuenta con|no dispone de)\s+'
                          r'(?:(?:un|una|ningun|ninguna)\s+)?' + noun + r'\b', text)
                or re.search(r'\b' + noun + r'\s*:\s*(?:false|0)\b', text)
                or re.search(r'\b' + noun + r'\s*:\s*no(?: tiene| cuenta(?: con)?| hay| dispone(?: de)?)?(?:$|[,.;])', text)
                or re.search(r'\b0\s+' + noun + r'\b', text)
                or (re.search(r'\bsin\b', text) and re.search(r'\bni\s+' + noun + r'\b', text)))


def _types(text):
    disposition = []
    if re.search(r'\b(?:lineal(?:es)?|en linea|tandem)\b', text):
        disposition.append('lineal')
    if re.search(r'\bparalel[oa]s?\b', text):
        disposition.append('paralela')
    uncovered = bool(re.search(r'\b(?:no techad[oa]s?|sin (?:techo|cubierta|techar)|descubiert[oa]s?|al aire libre)\b', text))
    roof_text = re.sub(r'\bno techad[oa]s?\b', '', text)
    covered = bool(re.search(r'\b(?:techad[oa]s?|cubiert[oa]s?)\b', roof_text))
    roof = None if uncovered == covered else not uncovered
    kind = (disposition[0] + ('_techada' if roof else '_no_techada')
            if len(disposition) == 1 and roof is not None else None)
    return kind, {'disposicion': disposition[0] if len(disposition) == 1 else None, 'techada': roof}


def _count(text):
    interval = NUM + r'\s*(?:-|–|a|al|o)\s*' + NUM
    if re.search(interval + r'\s*' + PARK, text) or re.search(PARK + r'\s*:\s*' + interval, text):
        return None
    before = re.search(r'\b(' + NUM + r')\s+' + PARK + r'\b', text)
    after = re.search(r'\b' + PARK + r'\s*:\s*(' + NUM + r')\b', text)
    match = before or after
    return _integer(match[1]) if match else None


def extract_features(kind, raw=None, description=None, count=None, amenities=None):
    raw = raw if isinstance(raw, dict) else {}
    applicable = plain(kind or '') in SUPPORTED
    parking = {'status': 'unknown' if applicable else 'not_applicable', 'has': None,
               'count': None, 'types': None, 'details': [], 'evidence': [], 'conditions': []}
    elevator = {'status': parking['status'], 'has': None, 'evidence': []}
    result = {'version': VERSION, 'parking': parking, 'elevator': elevator}
    if not applicable:
        return result
    presences, counts, types, elevators = set(), set(), set(), set()
    for field, original in _sources(raw, description, amenities):
        for _, text in _claims(field, original):
            if re.search(r'\b' + LIFT + r'\b', text):
                unknown = re.search(r'\b(?:preinstalacion|proyectad[oa]|futur[oa]|previst[oa]|por instalar|se instalara|no se (?:indica|especifica)|no (?:informad[oa]|especificad[oa]|declarad[oa])|sin (?:informacion|datos)|a consultar|posibilidad)\b', text)
                unknown = unknown or re.search(LIFT + r'\s*:\s*(?:$|[¿?])', text)
                if not unknown:
                    elevators.add(not _negative(text, LIFT))
                elevator['evidence'].append({'field': field, 'text': text[:260]})
            if not re.search(r'\b' + PARK + r'\b', text):
                continue
            parking['evidence'].append({'field': field, 'text': text[:260]})
            conditional = re.search(r'\b(?:opcional(?:es)?|adicional(?:es)?|precio aparte|costo aparte|se vende por separado|no incluid[oa]s?|visitas|visitantes|publico|publica|posibilidad|no se (?:indica|especifica)|no (?:informad[oa]|especificad[oa]|declarad[oa])|sin (?:informacion|datos)|a consultar|segun (?:la )?(?:unidad|disponibilidad))\b', text)
            conditional = conditional or re.search(PARK + r'\s*:\s*(?:$|[¿?])', text)
            if conditional:
                parking['conditions'].append({'field': field, 'text': text[:260]})
                continue
            negative = _negative(text, PARK)
            if negative:
                presences.add(False)
                counts.add(0)
                continue
            presences.add(True)
            # Explicitly connected groups can have different parking types.
            groups = re.split(r'\s+(?:y|mas)\s+(?=(?:otra|otro|una|un|\d+)\b)', text)
            group_counts = []
            for group in groups:
                if not re.search(r'\b' + PARK + r'\b', group) and len(groups) > 1:
                    group = re.sub(r'^(' + NUM + r')\b', r'\1 cochera', group)
                quantity = _count(group)
                group_counts.append(quantity)
                noun = re.search(r'\b' + PARK + r'\b', group)
                scope = group[noun.end():].split(',')[0] if noun else group
                category, detail = _types(scope)
                if category:
                    types.add(category)
                if any(v is not None for v in detail.values()):
                    parking['details'].append({'count': quantity, **detail})
            if group_counts and all(q is not None for q in group_counts):
                counts.add(sum(group_counts))
    # A stored positive count is useful for historical records; a default zero
    # does not prove absence without source evidence.
    recorded = _integer(count)
    if not counts and recorded is not None and recorded > 0 and not parking['conditions']:
        counts.add(recorded)
        presences.add(True)
    if len(presences) > 1 or (False in presences and types):
        parking['status'] = 'conflict'
    else:
        parking['has'] = next(iter(presences)) if presences else None
        parking['count'] = next(iter(counts)) if len(counts) == 1 else None
        parking['types'] = [k for k in PARKING_TYPES if k in types] or None
        if parking['has'] is False:
            parking.update(count=0, types=[])
        parking['status'] = ('conflict' if len(counts) > 1 else 'explicit'
                             if parking['has'] is not None and (parking['types'] or parking['has'] is False)
                             else 'partial' if parking['has'] is not None else 'unknown')
    if len(elevators) > 1:
        elevator['status'] = 'conflict'
    elif elevators:
        elevator.update(has=next(iter(elevators)), status='explicit')
    for feature in (parking, elevator):
        feature['evidence'] = feature['evidence'][:20]
    parking['details'] = parking['details'][:20]
    parking['conditions'] = parking['conditions'][:20]
    return result


def apply_features(row):
    raw = dict(row.get('datos_crudos') or {})
    result = extract_features(row.get('tipo_inmueble'), raw, row.get('descripcion'), row.get('estacionamientos'), row.get('amenities'))
    result['observed_at'] = str(row.get('fecha_extraccion') or '')
    raw['_building_features'] = result
    raw['tiene_cochera'] = result['parking']['has']
    raw['tipos_cochera'] = result['parking']['types']
    raw['tiene_ascensor'] = result['elevator']['has']
    if result['parking']['status'] != 'not_applicable':
        row['estacionamientos'] = result['parking']['count']
    row['datos_crudos'] = raw
    return row


def read_features(kind, raw, description=None, count=None, amenities=None):
    if plain(kind or '') not in SUPPORTED:
        return extract_features(kind)
    saved = raw.get('_building_features') if isinstance(raw, dict) else None
    valid = isinstance(saved, dict) and saved.get('version') == VERSION and all(
        isinstance(saved.get(k), dict) and saved[k].get('status') in
        ('unknown', 'partial', 'explicit', 'conflict', 'not_applicable') and
        (saved[k].get('has') is None or isinstance(saved[k].get('has'), bool))
        for k in ('parking', 'elevator'))
    parking = saved['parking'] if valid else {}
    types = parking.get('types')
    valid = valid and {'has', 'count', 'types'} <= parking.keys() and (
        parking['count'] is None or (_integer(parking['count']) is not None and not isinstance(parking['count'], bool))) and (
        types is None or isinstance(types, list) and all(isinstance(t, str) and t in PARKING_TYPES for t in types))
    if valid:
        return saved
    return extract_features(kind, raw, description, count, amenities)


def parking_label(feature):
    if feature['status'] == 'not_applicable':
        return '—'
    if feature['status'] == 'conflict':
        return 'Sin información · datos contradictorios'
    if feature['has'] is False:
        return 'Sin cochera'
    return ' + '.join(PARKING_TYPES[k] for k in (feature.get('types') or []) if k in PARKING_TYPES) or 'Sin información'


def yes_no(value):
    return 'Sí' if value is True else 'No' if value is False else 'Sin información'


def preserve_features(incoming, existing, protected=(), *, kind=None, description=None, count=None, amenities=None):
    """Keep confirmed history on incomplete reads, without hiding contradictions."""
    incoming = dict(incoming or {})
    current = deepcopy(incoming.get('_building_features') or {})
    if current.get('version') != VERSION:
        return incoming
    old = read_features(kind, existing, description, count, amenities)
    protected = set(protected)
    for name, fields in (('parking', {'tiene_cochera', 'tipos_cochera', 'estacionamientos'}),
                         ('elevator', {'tiene_ascensor'})):
        new, previous = current[name], old[name]
        if protected & fields:
            current[name] = deepcopy(previous)
            current[name]['protected'] = True
        elif new['status'] == 'unknown' and previous['has'] is not None:
            current[name] = deepcopy(previous)
            current[name]['reconfirmed'] = False
            current[name]['last_confirmed_at'] = old.get('observed_at', '')
        elif name == 'parking' and new['has'] is True and previous['has'] is True and new['status'] != 'conflict':
            for field in ('count', 'types'):
                if new.get(field) is None and previous.get(field) is not None:
                    new[field] = deepcopy(previous[field])
                    new['reconfirmed'] = False
                    new['last_confirmed_at'] = old.get('observed_at', '')
    incoming['_building_features'] = current
    incoming.update(tiene_cochera=current['parking']['has'], tipos_cochera=current['parking'].get('types'),
                    tiene_ascensor=current['elevator']['has'])
    return incoming
