"""Versioned, deterministic admission rules. This does not train or value a property."""
import hashlib
import json
import math
import re
import unicodedata

RULE_VERSION = 'offer-exact-v1'
FIELDS = ('fuente', 'id_origen', 'tipo_inmueble', 'tipo_operacion', 'precio_usd',
          'precio_soles', 'area_terreno', 'area_construida', 'antiguedad_anios',
          'dormitorios', 'banos', 'estacionamientos', 'latitud', 'longitud',
          'precision_ubicacion', 'distrito', 'provincia', 'departamento',
          'direccion_texto', 'estado_publicacion', 'descripcion', 'titulo', 'url')
LABELS = {'pending': 'Pendiente de evaluación', 'eligible': 'Candidata preliminar',
          'review': 'Necesita revisión', 'reference': 'Solo referencia',
          'excluded': 'Excluida por revisión humana', 'error': 'Error de evaluación'}


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError, OverflowError):
        return None


def plain(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').lower())
                   if not unicodedata.combining(c))


def digest(snapshot):
    material = {k: snapshot.get(k) for k in FIELDS}
    material['manual_excluded'] = bool(snapshot.get('manual_excluded'))
    material['manual_reason'] = snapshot.get('manual_reason') or ''
    material['normalizer_issues'] = snapshot.get('normalizer_issues') or []
    material['age_conflict'] = snapshot.get('age_conflict')
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), default=str).encode()).hexdigest()


def evaluate(row):
    reasons, notes = [], []
    def reason(code, message, field, severity='review'):
        reasons.append(dict(code=code, message=message, field=field, severity=severity))
    kind = row.get('tipo_inmueble')
    if row.get('manual_excluded'):
        reason('manual.excluded', row.get('manual_reason') or 'Excluida por revisión humana.', '', 'excluded')
    if row.get('tipo_operacion') != 'Venta':
        reason('operation.unsupported', 'Este conjunto es de precios de venta; la operación no es Venta.', 'tipo_operacion', 'reference')
    if kind not in ('Casa', 'Terreno', 'Departamento', 'Oficina'):
        severity = 'review' if kind in (None, '', 'Otro') else 'reference'
        reason('kind.unsupported', 'Tipo sin clasificar o fuera de los segmentos iniciales.', 'tipo_inmueble', severity)
    usd, pen = number(row.get('precio_usd')), number(row.get('precio_soles'))
    if usd is None or usd <= 0:
        reason('price.currency_pending' if pen and pen > 0 else 'price.missing',
               'Precio en soles: falta conversión fechada verificable a USD.' if pen and pen > 0
               else 'Falta un precio total de venta positivo.', 'precio_usd')
    for field in ('precio_usd', 'precio_soles'):
        if row.get(field) is not None and (number(row[field]) is None or number(row[field]) <= 0):
            reason('price.invalid', 'Precio no positivo o no numérico.', field)
    # Numeric fragments in prose do not override structured prices. Ambiguous sale
    # offers remain reviewable instead of being corrected toward a model output.
    title = plain(row.get('titulo'))
    if re.search(r'\b(?:cuota|remate|precio por m2|precio por metro)\b', title):
        reason('price.context', 'El título requiere comprobar si el precio corresponde al total anunciado.', 'precio_usd')
    land, built = number(row.get('area_terreno')), number(row.get('area_construida'))
    required = ('area_terreno', 'area_construida') if kind == 'Casa' else (
        ('area_terreno',) if kind == 'Terreno' else ('area_construida',) if kind in ('Departamento', 'Oficina') else ())
    for field in required:
        n = number(row.get(field))
        if n is None or n <= 0:
            reason('area.missing', 'Falta la superficie explícita requerida para este tipo.', field)
    # These are review reasons, not proof of a corrupt value or reasons to rewrite it.
    if kind == 'Casa' and land and land < 20:
        reason('area.small_land', 'Casa con terreno menor de 20 m²: contrastar con la ficha.', 'area_terreno')
    if kind == 'Casa' and land and built and built / land > 10:
        reason('area.ratio', 'Construcción mayor de diez veces el terreno: comprobar unidades y totalidad.', 'area_construida')
    lat, lng = number(row.get('latitud')), number(row.get('longitud'))
    if lat is None or lng is None or not (-19 <= lat <= 0 and -82 <= lng <= -68):
        reason('location.invalid', 'Coordenadas ausentes o fuera del ámbito geográfico de Perú.', 'latitud', 'reference')
    if row.get('precision_ubicacion') != 'exacta':
        reason('location.not_exact', 'Ubicación aproximada o sin precisión: se conserva como referencia.', 'precision_ubicacion', 'reference')
    else:
        notes.append('Exacta declarada: no equivale a ubicación catastral verificada.')
    age = number(row.get('antiguedad_anios'))
    if row.get('antiguedad_anios') is None:
        notes.append('Antigüedad desconocida; no se imputa como cero.')
    elif age is None or age < 0 or age > 150:
        reason('age.invalid', 'Antigüedad fuera del rango admitido de 0 a 150 años.', 'antiguedad_anios')
    if row.get('age_conflict'):
        reason('age.conflict', 'Evidencia de antigüedad ambigua, contradictoria o sin fecha válida.', 'antiguedad_anios')
    for field in row.get('normalizer_issues') or []:
        # Archived warnings about optional fields (e.g. a missing PEN price when
        # USD exists) must not reject an otherwise usable current record.
        if field in (*required, 'precio_usd') and not (number(row.get(field)) or 0) > 0:
            reason('source.invalid_value', 'El normalizador detectó un valor inválido en un campo requerido.', str(field))
        else:
            notes.append('Advertencia conservada de la extracción original: ' + str(field) + '.')
    if row.get('estado_publicacion') == 'retirada':
        notes.append('Anuncio retirado: evidencia histórica; no demuestra una venta cerrada.')
    if row.get('estado_publicacion') in (None, '', 'sin_verificar', 'posible_retirada'):
        notes.append('La presencia actual del anuncio no está confirmada.')
    priorities = ('excluded', 'reference', 'review')
    status = next((s for s in priorities if any(r['severity'] == s for r in reasons)), 'eligible')
    notes.append('Identidad entre portales y microzona pendientes de validación; aún no utilizada en un modelo.')
    return dict(status=status, reasons=reasons, notes=notes, rule_version=RULE_VERSION)
