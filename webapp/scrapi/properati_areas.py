"""Read the current listing's surface, excluding descriptions and similar ads."""
import re

from bs4 import BeautifulSoup

from .areas import calcular_areas
from .area_evidence import MEASURE, numeric_area, text


def detail_area(html):
    soup = BeautifulSoup(html or '', 'html.parser')
    values = set()
    for node in soup.select('.place-details [data-test="area-value"]'):
        if any(re.search(r'similar|recommend|related|snippet',
                         ' '.join(parent.get('class', [])), re.I)
               for parent in node.parents):
            continue
        raw = node.get_text(' ', strip=True)
        value = numeric_area(raw)
        if value is not None:
            values.add(value)
    return next(iter(values)) if len(values) == 1 else None


def property_areas(prop):
    result = calcular_areas(prop)
    if result['area_terreno'] is not None or result['area_construida'] is not None:
        return result
    # An unlabelled surface in prose may describe a storage room or parking
    # space. It cannot become the surface used to value the entire property.
    content = text(' '.join(str(prop.get(key) or '') for key in
                           ('Descripcion', 'Caracteristicas', 'Titulo')))
    values = set()
    accessory = r'(?:deposito|cochera|estacionamiento|balcon|terraza|dormitorio|habitacion|bano|cocina|sala|comedor)'
    for match in MEASURE.finditer(content):
        before = content[max(0, match.start()-60):match.start()]
        after = content[match.end():match.end()+50]
        if (re.search(r'\b' + accessory + r'(?:\s+(?:de|con|un|unos|aprox|aproximadamente))*\s*$', before)
                or re.match(r'\s*(?:de\s+)?' + accessory + r'\b', after)):
            continue
        value = numeric_area(match.group())
        if value is not None:
            values.add(value)
    # Preserve the shared parser's rejection of ranges and other ambiguous
    # descriptions; only refine an already accepted generic fallback.
    if result['area_m2'] is not None:
        result['area_m2'] = next(iter(values)) if len(values) == 1 else None
    return result
