"""Conservative numeric and property normalization; raw evidence stays intact."""
import math
import re
import unicodedata
from datetime import datetime
from numbers import Number
from urllib.parse import urlsplit

from .areas import calcular_areas


def plain(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').lower())
                   if not unicodedata.combining(c))


def number(value):
    if isinstance(value, Number):
        return float(value) if math.isfinite(float(value)) else None
    raw = re.sub(r'[^\d,.-]', '', str(value or ''))
    if not raw:
        return None
    if ',' in raw and '.' in raw:
        decimal = ',' if raw.rfind(',') > raw.rfind('.') else '.'
        raw = raw.replace('.' if decimal == ',' else ',', '').replace(decimal, '.')
    elif ',' in raw or '.' in raw:
        sep = ',' if ',' in raw else '.'
        chunks = raw.split(sep)
        if len(chunks) > 2 or (len(chunks) == 2 and len(chunks[-1]) == 3):
            raw = ''.join(chunks)
        else:
            raw = raw.replace(sep, '.')
    try:
        parsed = float(raw)
        return parsed if math.isfinite(parsed) else None
    except ValueError:
        return None


def prices(text):
    result = {'precio_soles': None, 'precio_usd': None}
    for match in re.finditer(r"(US\$|USD|S/\.?|PEN|\$)\s*([\d][\d.,'’ ]*)", str(text or ''), re.I):
        key = 'precio_soles' if match[1].upper() in ('S/', 'S/.', 'PEN') else 'precio_usd'
        result[key] = number(match[2])
    return result


def property_type(text):
    text = plain(text)
    for label, pattern in (
        ('Departamento', r'\b(departamentos?|apartamentos?|apartments?|duplex|flat)\b'),
        ('Terreno', r'\b(terrenos?|lotes?)\b'), ('Casa', r'\b(casas?|chalet|house|villa)\b'),
        ('Local', r'\b(locales?|tiendas?|almacen)\b'), ('Oficina', r'\b(oficinas?|consultorios?)\b'),
        ('Hotel', r'\b(hoteles?|hostales?)\b')):
        if re.search(pattern, text):
            return label
    return None


def operation(text):
    text = plain(text)
    if 'alquiler' in text or 'arriendo' in text:
        return 'Alquiler'
    if 'venta' in text:
        return 'Venta'
    return None


def listing_operation(raw):
    """A detail URL/type overrides the search page, which can contain recommendations."""
    for key in ('Operacion', 'operacion', 'tipo_operacion'):
        result = operation(raw.get(key))
        if result:
            return result
    detail_url = raw.get('URL Propiedad') or raw.get('url') or raw.get('URL') or ''
    path = urlsplit(str(detail_url)).path
    if re.search(r'/alcl', path):
        return 'Alquiler'
    if re.search(r'/vecl', path):
        return 'Venta'
    result = operation(path)
    if result:
        return result
    for key in ('Tipo', 'tipo', 'Titulo', 'titulo'):
        result = operation(raw.get(key))
        if result:
            return result
    return operation(raw.get('_source_url'))


def construction_age(raw, extracted_at=None):
    """Use explicit age/build-year evidence; never infer age from marketing dates."""
    raw = raw if isinstance(raw, dict) else {}
    structured = []
    new_conditions = []
    invalid_age_labels = []
    unfinished = False

    def read_condition(value, key):
        nonlocal unfinished
        label = re.sub(r'\s+', ' ', plain(value)).strip()
        if re.fullmatch(r'(?:antiguedad\s*[:=\-]?\s*)?(?:a estrenar|de estreno|estreno)', label):
            new_conditions.append({'label': key, 'value': str(value).strip()})
        elif re.fullmatch(r'(?:antiguedad\s*[:=\-]?\s*)?(?:en construccion|en proyecto|proyecto|en pozo)', label):
            unfinished = True

    for key in ('Antiguedad', 'antiguedad', 'Antigüedad', 'antiguedad_anios'):
        value = raw.get(key)
        read_condition(value, key)
        match = re.fullmatch(r'\s*(\d{1,3})\s*(?:años?|years?)?\s*', str(value or ''), re.I)
        if value == 0:
            match = re.fullmatch(r'(\d+)', '0')
        if match and int(match.group(1)) <= 150:
            structured.append((int(match.group(1)), key, str(value)))
        elif re.search(r'\d', str(value or '')):
            invalid_age_labels.append({'label': key, 'value': str(value)})
    # A standalone feature chip ("13 años") is a portal age field, not
    # description prose such as "13 años de experiencia" or delivery dates.
    for key in ('Caracteristicas', 'caracteristicas'):
        features = raw.get(key)
        labels = features if isinstance(features, (list, tuple)) else re.split(r'[|\n\r]', str(features or ''))
        for label in labels:
            read_condition(label, key)
            match = re.fullmatch(r'\s*(?:antiguedad\s*:?\s*)?(\d{1,3})\s*anos?(?:\s+de\s+antiguedad)?\s*', plain(label))
            if match and int(match.group(1)) <= 150:
                structured.append((int(match.group(1)), key, str(label).strip()))
            elif re.search(r'\d.*\banos?\b', plain(label)):
                invalid_age_labels.append({'label': key, 'value': str(label).strip()})
    # Only an explicitly labelled age in prose is accepted. Titles and
    # marketing phrases ("como nueva", "remodelada") never imply zero years.
    for key in ('Descripcion', 'descripcion', 'description', 'visible_text_excerpt'):
        for match in re.finditer(r'\bantig[uü]edad\s*[:=]\s*(a\s+estrenar|de\s+estreno|estreno)\b', str(raw.get(key) or ''), re.I):
            read_condition(match.group(1), key)
    parts = [raw.get(key) for key in ('Descripcion', 'descripcion', 'description',
             'Caracteristicas', 'caracteristicas', 'Caracteristicas Extra', 'visible_text_excerpt')]
    normalized = plain(' '.join(str(v) for v in parts if v))
    building_text = normalized + ' ' + plain(raw.get('tipo_inmueble') or raw.get('Tipo') or '')
    has_building = bool(re.search(r'\b(?:casas?|viviendas?|departamentos?|edificios?|locales?|oficinas?|construid[oa]s?|construccion|edificad[oa]s?)\b', building_text))
    ages = set()
    if has_building:
        for pattern in (r'\bantiguedad\s*[:=]?\s*(\d{1,3})\s*anos\b', r'\b(\d{1,3})\s*anos\s+de\s+antiguedad\b'):
            ages.update(int(m.group(1)) for m in re.finditer(pattern, normalized))
    years = set()
    for pattern in (r'\bano\s+(?:de\s+)?(?:construccion|edificacion)\s*[:=\-]?\s*(19\d{2}|20\d{2})\b',
                    r'\b(?:construid[oa]|edificad[oa])\s+en\s+(19\d{2}|20\d{2})\b',
                    r'\bano\s+en\s+que\s+fue\s+construid[oa]\s*[:=\-]?\s*(19\d{2}|20\d{2})\b'):
        years.update(int(m.group(1)) for m in re.finditer(pattern, normalized))
    evidence = {'source': 'description_age', 'values': sorted(ages), 'construction_years': sorted(years)}
    if new_conditions:
        evidence['new_condition_claims'] = new_conditions

    def record_condition_conflict(age):
        if new_conditions and age != 0:
            evidence['condition_conflict'] = 'numeric_age_overrides_new_condition'
    reference_year = None
    if years:
        try:
            reference_year = extracted_at.year if isinstance(extracted_at, datetime) else datetime.fromisoformat(str(extracted_at).replace('Z', '+00:00')).year
        except (ValueError, TypeError):
            evidence['reason'] = 'invalid_extraction_date'
        if reference_year:
            evidence['reference_year'] = reference_year
            ages.update(reference_year - year for year in years)
    all_ages = ages | {age for age, _, _ in structured}
    if len(all_ages) > 1 or len(years) > 1:
        evidence['reason'] = 'conflicting_age_values'
        evidence['values'] = sorted(all_ages)
    elif all_ages and not 0 <= next(iter(all_ages)) <= 150:
        evidence['reason'] = 'age_out_of_range'
    if structured:
        age, key, value = structured[0]
        evidence.update(source='portal_age_field', label=key, value=value)
        # Conflicts stay visible but description evidence never rewrites a portal field.
        if len({a for a, _, _ in structured}) > 1:
            return None, evidence
        record_condition_conflict(age)
        return age, evidence
    if evidence.get('reason'):
        return None, evidence
    if not ages:
        if new_conditions:
            if unfinished or invalid_age_labels:
                evidence['reason'] = 'conflicting_property_condition' if unfinished else 'invalid_explicit_age'
                if invalid_age_labels:
                    evidence['invalid_age_labels'] = invalid_age_labels
                return None, evidence
            evidence.update(source='portal_new_condition', years=0, **new_conditions[0])
            return 0, evidence
        return None, None
    age = next(iter(ages))
    evidence['source'] = 'description_construction_year' if years else 'description_age'
    evidence['years'] = age
    if years:
        evidence['year'] = next(iter(years))
    record_condition_conflict(age)
    return age, evidence


def urbania_row(prop, stamp):
    feats = str(prop.get('Caracteristicas') or '')
    # Área de terreno y construida, cada una por su lado (campos del portal y,
    # si faltan, el texto de características: "128 m2 totales / 90 m2 construidos").
    detalle_areas = calcular_areas({**prop, 'Caracteristicas': feats})
    # Un rango describe varias unidades; no se convierte un extremo en área exacta.
    if re.search(r'\d\s*(?:-|–|a)\s*\d[\d.,]*\s*m[²2]', feats):
        detalle_areas = {'area_terreno': None, 'area_construida': None, 'area_m2': None}
    def count(pattern):
        match = re.search(pattern, feats, re.I)
        return int(match[1]) if match else None
    location = [p.strip() for p in str(prop.get('Ubicacion') or '').split(',') if p.strip()]
    coords = str(prop.get('Coordenadas') or '').split(',')
    lat = lng = None
    if len(coords) == 2:
        try:
            lat, lng = map(float, coords)
        except ValueError:
            pass
    title = str(prop.get('Titulo') or '').strip()
    age, age_evidence = construction_age(prop, stamp)
    row = {
        'fuente': 'urbania', 'id_origen': str(prop.get('ID') or '').strip(),
        'fecha_extraccion': stamp, 'titulo': title or None,
        'tipo_inmueble': property_type(f'{prop.get("Tipo", "")} {title}'),
        'tipo_operacion': listing_operation(prop),
        **prices(prop.get('Precio')),
        'area_m2': detalle_areas['area_m2'],
        'area_terreno': detalle_areas['area_terreno'],
        'area_construida': detalle_areas['area_construida'],
        'dormitorios': count(r'(\d+)\s*dorm'), 'banos': count(r'(\d+)\s*bañ'),
        'estacionamientos': count(r'(\d+)\s*(?:estac|coch)'),
        'departamento': location[-1] if len(location) >= 3 else None,
        'provincia': location[-2] if len(location) >= 3 else (location[-1] if len(location) == 2 else None),
        'distrito': location[0] if location else None, 'direccion_texto': prop.get('Direccion') or None,
        'latitud': lat, 'longitud': lng, 'descripcion': prop.get('Descripcion') or None,
        'url': prop.get('URL Propiedad') or prop.get('URL') or prop.get('url'),
        'imagen_url': prop.get('Imagen URL') or None, 'datos_crudos': dict(prop),
        'antiguedad_anios': age,
    }
    result = validate_row(row)
    if age_evidence:
        result['datos_crudos']['_age_evidence'] = age_evidence
    return result


def validate_row(row):
    row = dict(row)
    if not str(row.get('id_origen') or '').strip():
        raise ValueError('listing.missing_id: publicación sin ID estable')
    issues = []
    for field in ('precio_soles', 'precio_usd', 'area_m2', 'area_terreno', 'area_construida'):
        value = row.get(field)
        if value is not None and (not math.isfinite(float(value)) or float(value) <= 0):
            issues.append(field)
            row[field] = None
    lat, lng = row.get('latitud'), row.get('longitud')
    if lat is not None or lng is not None:
        if lat is None or lng is None or not (-90 <= float(lat) <= 90 and -180 <= float(lng) <= 180):
            issues.append('coordinates')
            row['latitud'] = row['longitud'] = None
    raw = dict(row.get('datos_crudos') or {})
    raw['_normalizer_version'] = '3'
    if issues:
        raw['_quality_issues'] = issues
    row['datos_crudos'] = raw
    return row
