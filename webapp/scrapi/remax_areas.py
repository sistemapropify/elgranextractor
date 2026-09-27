"""Superficies REMAX: campos explícitos y descripción solo para completar vacíos."""
import logging
import math
import re
import unicodedata
from numbers import Number

logger = logging.getLogger(__name__)
VERSION = 'remax-areas-1'
NUMBER = r"(?:\d{1,3}(?:[ '’]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)*)"
UNIT = r'(?:m\s*(?:2|\^2)|mts?\.?\s*2|metros?\s+cuadrados?|ha\b|hectareas?\b)'
MEASURE = re.compile(rf'(?<![\w.,])(?P<value>{NUMBER})\s*(?P<unit>{UNIT})(?!\w)')
LABELS = {
    'area_terreno': r'(?:area\s+(?:de(?:l)?\s+)?terreno|superficie\s+(?:de(?:l)?\s+)?terreno|terreno|lote|a\.?\s*t\.?)',
    'area_construida': r'(?:area\s+(?:construida|techada|edificada|de\s+construccion)|superficie\s+(?:construida|techada)|construccion|a\.?\s*c\.?)',
}
CONNECTOR = r'\s*(?:(?:total|imponente|aproximad[oa]|aprox\.?|es|de|del|con|tiene|cuenta\s+con)\s*)*[:=]?\s*'
PREFIX = {key: re.compile(rf'(?<!\w){label}{CONNECTOR}$') for key, label in LABELS.items()}
SUFFIX = {
    'area_terreno': re.compile(r'^\s*(?:de\s+)?(?:area\s+de\s+)?(?:terreno|lote)\b'),
    'area_construida': re.compile(r'^\s*(?:(?:de\s+)?(?:area\s+)?(?:construccion|construid[oa]s?|techad[oa]s?|edificad[oa]s?))\b'),
}
FIELDS = {'area_terreno': ('Area Terreno', 'Área Terreno'),
          'area_construida': ('Area Construida', 'Área Construida')}


def plain(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').lower())
                   if not unicodedata.combining(c) and c not in '\u200b\ufeff')


def numeric(raw):
    raw = re.sub(r"[ '’]", '', raw)
    if ',' in raw and '.' in raw:
        decimal = ',' if raw.rfind(',') > raw.rfind('.') else '.'
        thousands = '.' if decimal == ',' else ','
        # Reject malformed grouping instead of salvaging part of the number.
        if not re.fullmatch(rf'\d{{1,3}}(?:{re.escape(thousands)}\d{{3}})+{re.escape(decimal)}\d{{1,2}}', raw):
            return None
        raw = raw.replace(thousands, '').replace(decimal, '.')
    elif ',' in raw or '.' in raw:
        separator = ',' if ',' in raw else '.'
        parts = raw.split(separator)
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            raw = '.'.join(parts)
        elif len(parts[0]) <= 3 and all(len(p) == 3 for p in parts[1:]):
            raw = ''.join(parts)
        else:
            return None
    try:
        number = float(raw)
        return number if math.isfinite(number) and number > 0 else None
    except (ValueError, OverflowError):
        return None


def parse_area(value):
    if isinstance(value, Number) and not isinstance(value, bool):
        number = float(value)
        return number if math.isfinite(number) and number > 0 else None
    match = re.fullmatch(rf'\s*(?P<value>{NUMBER})\s*(?P<unit>{UNIT})?\s*[.]?\s*', plain(value))
    if not match:
        return None
    number = numeric(match['value'])
    unit = match['unit'] or ''
    return number * (10000 if unit.startswith(('ha', 'hectarea')) else 1) if number else None


def description_areas(description):
    """Accept explicit associations only, with evidence and no guessed generic m²."""
    text = plain(description)
    candidates = {key: [] for key in FIELDS}
    issues = []
    for match in MEASURE.finditer(text):
        before, after = text[max(0, match.start()-100):match.start()], text[match.end():match.end()+85]
        # Never take one endpoint of a range or a surface per floor/unit.
        range_before = re.search(rf'{NUMBER}\s*(?:{UNIT})?\s*(?:-|–|a|hasta|y)\s*$', before)
        range_after = re.match(rf'\s*(?:-|–|a|hasta)\s*{NUMBER}', after)
        variable = re.search(r'\b(?:desde|entre)\s*$', before)
        per_unit = re.match(r'\s*(?:por\s+(?:piso|nivel|unidad)|cada\s+un[oa])\b', after)
        if range_before or range_after or variable or per_unit:
            continue
        value = parse_area(match.group())
        if value is None:
            continue
        for key in FIELDS:
            prefix, suffix = PREFIX[key].search(before), SUFFIX[key].search(after)
            if not prefix and not suffix:
                continue
            # Subdivisions of land are evidence, not a replacement for its total.
            if key == 'area_terreno' and re.match(r'\s*(?:urbanos|rusticos)\b', after):
                continue
            start = max(0, match.start()-100) + prefix.start() if prefix else match.start()
            end = match.end() + suffix.end() if suffix else match.end()
            candidates[key].append({'value': value, 'text': text[start:end]})
    found = {}
    for key, items in candidates.items():
        values = {item['value'] for item in items}
        if len(values) == 1:
            found[key] = items[0]
        elif len(values) > 1:
            issues.append({'field': key, 'reason': 'description_conflict', 'candidates': items})
    return found, issues


def calcular_areas_remax(prop):
    """Preserve explicit fields; resolve each missing area independently."""
    result = {key: None for key in FIELDS}
    evidence = {'version': VERSION, 'fields': {}, 'issues': []}
    for key, labels in FIELDS.items():
        for label in labels:
            value = parse_area(prop.get(label))
            if value is not None:
                result[key] = value
                evidence['fields'][key] = {'source': 'portal_field', 'label': label,
                                          'raw': str(prop[label]), 'value': value}
                break
    missing = [key for key in FIELDS if result[key] is None]
    if missing:
        found, issues = description_areas(prop.get('Descripcion'))
        evidence['issues'] = [issue for issue in issues if issue['field'] in missing]
        for key in missing:
            if key in found:
                result[key] = found[key]['value']
                evidence['fields'][key] = {'source': 'detail_description', **found[key]}
                logger.info('remax.area.completed id=%s field=%s value=%s source=detail_description',
                            prop.get('ID'), key, result[key])
    # Keep the legacy dimensions fallback only for a single explicit pair.
    if result['area_terreno'] is None and not any(i['field'] == 'area_terreno' for i in evidence['issues']):
        dimensions = re.fullmatch(rf'\s*({NUMBER})\s*[x×]\s*({NUMBER})\s*', plain(prop.get('Medidas')))
        if dimensions:
            width, depth = numeric(dimensions[1]), numeric(dimensions[2])
            if width and depth:
                result['area_terreno'] = round(width * depth, 2)
                evidence['fields']['area_terreno'] = {'source': 'dimensions',
                    'raw': str(prop['Medidas']), 'value': result['area_terreno']}
    if evidence['issues']:
        logger.warning('remax.area.unresolved id=%s fields=%s reason=description_conflict',
                       prop.get('ID'), [i['field'] for i in evidence['issues']])
    prop['_area_evidence'] = evidence
    land_first = any(word in plain(prop.get('Tipo')) for word in ('terreno', 'lote', 'parcela', 'chacra'))
    primary, secondary = ('area_terreno', 'area_construida') if land_first else ('area_construida', 'area_terreno')
    result['area_m2'] = result[primary] or result[secondary]
    return result
