"""Conservative numeric and property normalization; raw evidence stays intact."""
import math
import re
import unicodedata
from numbers import Number


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


def urbania_row(prop, stamp):
    feats = str(prop.get('Caracteristicas') or '')
    areas = re.findall(r'(?<![\d.,])([\d]+(?:[.,][\d]+)*)\s*m[²2]', feats, re.I)
    # A range describes several units; do not turn one endpoint into an exact area.
    area_range = bool(re.search(r'\d\s*(?:-|–|a)\s*\d[\d.,]*\s*m[²2]', feats))
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
    row = {
        'fuente': 'urbania', 'id_origen': str(prop.get('ID') or '').strip(),
        'fecha_extraccion': stamp, 'titulo': title or None,
        'tipo_inmueble': property_type(f'{prop.get("Tipo", "")} {title}'),
        'tipo_operacion': operation(f'{prop.get("Operacion", "")} {title} {prop.get("_source_url", "")}'),
        **prices(prop.get('Precio')), 'area_m2': number(areas[0]) if areas and not area_range else None,
        'dormitorios': count(r'(\d+)\s*dorm'), 'banos': count(r'(\d+)\s*bañ'),
        'estacionamientos': count(r'(\d+)\s*(?:estac|coch)'),
        'departamento': location[-1] if len(location) >= 3 else None,
        'provincia': location[-2] if len(location) >= 3 else (location[-1] if len(location) == 2 else None),
        'distrito': location[0] if location else None, 'direccion_texto': prop.get('Direccion') or None,
        'latitud': lat, 'longitud': lng, 'descripcion': prop.get('Descripcion') or None,
        'url': prop.get('URL Propiedad') or prop.get('URL') or prop.get('url'),
        'imagen_url': prop.get('Imagen URL') or None, 'datos_crudos': dict(prop),
    }
    return validate_row(row)


def validate_row(row):
    row = dict(row)
    if not str(row.get('id_origen') or '').strip():
        raise ValueError('listing.missing_id: publicación sin ID estable')
    issues = []
    for field in ('precio_soles', 'precio_usd', 'area_m2'):
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
    raw['_normalizer_version'] = '2'
    if issues:
        raw['_quality_issues'] = issues
    row['datos_crudos'] = raw
    return row
