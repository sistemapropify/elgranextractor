"""Apartment location within a building, never the building's floor count."""
import re
import unicodedata


VERSION = 1
WORDS = {
    'primer': 1, 'primero': 1, 'primera': 1, 'segundo': 2, 'segunda': 2,
    'tercer': 3, 'tercero': 3, 'tercera': 3, 'cuarto': 4, 'cuarta': 4,
    'quinto': 5, 'quinta': 5, 'sexto': 6, 'sexta': 6, 'septimo': 7,
    'septima': 7, 'setimo': 7, 'setima': 7, 'octavo': 8, 'octava': 8,
    'noveno': 9, 'novena': 9, 'decimo': 10, 'decima': 10,
    'undecimo': 11, 'onceavo': 11, 'duodecimo': 12, 'doceavo': 12,
    'decimotercero': 13, 'decimocuarto': 14, 'decimoquinto': 15,
    'decimosexto': 16, 'decimoseptimo': 17, 'decimoctavo': 18,
    'decimonoveno': 19, 'vigesimo': 20,
}
WORDS.update({'decimo ' + word: 10 + value for word, value in list(WORDS.items()) if value < 10})
TOKEN = r'(?:\d{1,3}(?:\.?\s*(?:[º°ª]|ero|era|er|ro|ra|do|da|to|ta|mo|ma|vo|va|no|na|avo|ava))?|' + '|'.join(sorted(WORDS, key=len, reverse=True)) + ')'
LOCATION = re.compile(r'\bpisos?\s*(?:n(?:ro|umero|o)?\.?\s*[°º]?\s*|#\s*)?[:=]?\s*(' + TOKEN + r')(?:\s*(?:,\s*|y\s+)(' + TOKEN + r'))?(?:\s*y\s+(' + TOKEN + r'))?\b')
ORDINAL = re.compile(r'(?<![\w.])(' + TOKEN + r')(?:\s*(?:,\s*|y\s+)(' + TOKEN + r'))?(?:\s*y\s+(' + TOKEN + r'))?\s+piso\b')
SPECIAL = re.compile(r'\b(planta\s+baja|semisotano|sotano(?:\s+[12])?)\b')
STRUCTURED = ('Piso', 'piso', 'Floor', 'floor', 'floorNumber', 'floor_number',
              'Piso del departamento', 'Nivel del departamento')
TEXT_FIELDS = ('Descripcion', 'descripcion', 'description', 'Titulo', 'titulo', 'title',
               'Caracteristicas', 'caracteristicas', 'Caracteristicas Extra', 'features')


def plain(value):
    value = re.sub(r'(?<=\d)\.?\s*[º°ª]', '', str('' if value is None else value))
    return ''.join(c for c in unicodedata.normalize('NFKD', value.lower())
                   if not unicodedata.combining(c))


def number(value):
    value = value.strip()
    if value in WORDS:
        return WORDS[value]
    match = re.match(r'^\d{1,3}', value)
    result = int(match.group()) if match else None
    return result if result is not None and 0 <= result <= 200 else None


def extract_floor(kind, raw=None, description='', title=''):
    """Return a canonical string and the short passage supporting it."""
    if plain(kind) not in ('departamento', 'apartamento', 'duplex', 'triplex', 'flat'):
        return None, None
    raw = raw if isinstance(raw, dict) else {}
    texts = [(key, str(raw[key])) for key in TEXT_FIELDS if isinstance(raw.get(key), (str, int))]
    texts += [('descripcion', str(description or '')), ('titulo', str(title or ''))]
    multi_level = any(re.search(r'\b(?:duplex|triplex)\b', plain(value)) for _, value in texts)
    candidates = []
    keys = STRUCTURED + (() if raw.get('_floor_evidence') else ('piso_departamento',))
    for key in keys:
        value = raw.get(key)
        if value is None or isinstance(value, (dict, list, bool)):
            continue
        if isinstance(value, (int, float)):
            if not float(value).is_integer() or not 0 <= value <= 200:
                continue
            value = str(int(value))
        value = plain(value).strip()
        direct = re.fullmatch(TOKEN, value)
        if direct and number(value) is not None:
            candidates.append((str(number(value)), key, str(raw[key])[:180]))
        else:
            texts.append((key, 'piso ' + value))
    for field, original in texts:
        content = plain(original)
        occupied = []
        for pattern in (LOCATION, ORDINAL):
            for match in pattern.finditer(content):
                if any(match.start() < end and match.end() > start for start, end in occupied):
                    continue
                before, after = content[max(0, match.start()-50):match.start()], content[match.end():match.end()+30]
                # Interior level headings in duplex descriptions and references
                # to a building or lift do not identify this apartment's floor.
                if (re.match(r'\s*:', after)
                        or re.match(r'[.,]\d', after)
                        or re.search(r'\b(?:edificio|edificacion|torre|ascensor)\s+(?:de\s+)?$', before)
                        or re.search(TOKEN + r'\s*(?:a|al|hasta|-)\s*$', before)
                        or re.search(r'\b(?:cocheras?|estacionamientos?|depositos?|ascensor)\s+(?:en|hasta|al)\s+(?:el\s+)?$', before)
                        or re.search(r'\b(?:desde|entre)\s*$', before)
                        or re.match(r'\s*(?:a|al|hasta|-)\s*\d', after)):
                    continue
                levels = [number(value) for value in match.groups() if value]
                if not levels or any(value is None for value in levels):
                    continue
                occupied.append(match.span())
                if len(levels) > 1 and not multi_level:
                    candidates.append((None, field, original[max(0,match.start()-25):match.end()+25]))
                else:
                    candidates.append((' y '.join(map(str, sorted(set(levels)))), field,
                                       original[max(0,match.start()-25):match.end()+25]))
        for match in SPECIAL.finditer(content):
            before = content[max(0, match.start()-45):match.start()]
            if re.search(r'\b(?:cocheras?|estacionamientos?|depositos?|ascensor|acceso)\b', before):
                continue
            labels = {'planta baja': 'Planta baja', 'semisotano': 'Semisótano'}
            value = labels.get(match.group(), 'Sótano' + match.group()[6:])
            candidates.append((value, field, original[max(0,match.start()-25):match.end()+25]))
    values = {value for value, _, _ in candidates}
    if not values:
        return None, None
    evidence = {'version': VERSION, 'source': candidates[0][1], 'text': candidates[0][2].strip()[:180]}
    if len(values) != 1 or None in values:
        return None, {**evidence, 'status': 'ambiguous'}
    return next(iter(values)), {**evidence, 'status': 'explicit'}
