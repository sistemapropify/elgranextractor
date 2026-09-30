"""Read complete measurements, with adjacent labels rather than nearby numbers."""
import re
from .remax_areas import NUMBER, UNIT, parse_area, plain


def text(value):
    value = plain(value)
    # HTML text can concatenate the unit and the next field heading.
    value = re.sub(r'(m\s*2)(?=[a-z])', r'\1 ', value)
    # Normalize the WHOLE numeric token: 2, 989. 17 must become 2,989.17,
    # never leave a prefix behind and salvage 989.17 as the surface.
    return re.sub(rf'(?<![\w.,])\d+(?:[.,]\s*\d+)+(?=\s*(?:{UNIT})(?!\w))',
                  lambda m: re.sub(r'\s+', '', m.group()), value)


def numeric_area(value):
    if isinstance(value, str):
        value = text(value)
        value = re.sub(r'(?<=\d)([.,])\s+(?=\d{1,3}\s*$)', r'\1', value)
        # Structured portal fields can carry their own unit label.
        value = re.sub(r'\s+(?:tot(?:al(?:es)?)?|cub(?:iert[oa]s?)?)\.?\s*$', '', value)
    return parse_area(value)


MEASURE = re.compile(rf'(?<![\w.,])(?P<number>{NUMBER})\s*(?P<unit>{UNIT})(?!\w)')
PREFIX = {
    'area_terreno': re.compile(r'(?:\barea\s+(?:total\s+)?(?:de(?:l)?\s+)?terreno|\bsuperficie\s+(?:de(?:l)?\s+)?terreno|\bterreno|\blote)\s*[:=]?\s*$'),
    'area_construida': re.compile(r'(?:\barea\s+(?:total\s+)?(?:construida|techada|edificada|de\s+construccion)|\bsuperficie\s+(?:construida|techada)|\bconstruccion|\bconstruid[oa]s?)\s*[:=]?\s*$'),
}
SUFFIX = {
    'area_terreno': re.compile(r'^\s*(?:(?:de\s+)?terreno|totales?|tot\.?)(?!\w)'),
    'area_construida': re.compile(r'^\s*(?:(?:de\s+)?(?:area\s+)?construccion|(?:de\s+area\s+)?construid[oa]s?|techad[oa]s?|cub(?:iert[oa]s?)?\.?)(?!\w)'),
}


def description_areas(value):
    normalized = text(value)
    found = {key: [] for key in PREFIX}
    for match in MEASURE.finditer(normalized):
        before = normalized[max(0, match.start()-90):match.start()]
        after = normalized[match.end():match.end()+60]
        if (re.search(rf'{NUMBER}\s*(?:{UNIT})?\s*(?:-|–|a|hasta)\s*$', before)
                or re.match(rf'\s*(?:-|–|a|hasta)\s*{NUMBER}', after)
                or re.search(r'\b(?:desde|entre)\s*$', before)
                or re.match(r'\s*(?:libres?|por\s+(?:piso|nivel|unidad)|cada\s+un[oa])\b', after)):
            continue
        # Area per floor is not the total construction of the property.
        if re.search(r'\b(?:primer|segundo|tercer|\d+(?:er|do|ro|to)?)\s*(?:piso|nivel)\s*[:(\-]*\s*$', before):
            continue
        area = numeric_area(match.group())
        if area is None:
            continue
        for key in found:
            prefix, suffix = PREFIX[key].search(before), SUFFIX[key].search(after)
            # "Terreno: 286 m² Construidos: 140 m²": Construidos labels
            # the NEXT number, not the previous surface.
            if suffix and re.match(rf'\s*[:=]\s*{NUMBER}', after[suffix.end():]):
                suffix = None
            # An explicit prefix takes precedence over a contradictory suffix,
            # e.g. "Área construida: 270 m² totales" is not land.
            if suffix and any(PREFIX[other].search(before) for other in PREFIX if other != key):
                suffix = None
            if prefix or suffix:
                found[key].append((2 if prefix else 1, area))
    result = {}
    for key, candidates in found.items():
        rank = max((rank for rank, _ in candidates), default=0)
        values = {area for priority, area in candidates if priority == rank}
        # Competing totals remain unknown; never silently choose a room/level.
        result[key] = values.pop() if len(values) == 1 else None
    return result
