"""The quality dashboard and map share the same explainable alert rules."""
import re
from decimal import Decimal, InvalidOperation
from cuadrantizacion.property_quality import annotate_map_quality
from scrapi.areas import ETIQUETAS_TERRENO, ETIQUETAS_CONSTRUIDA, extraer_area_etiquetada

DATA_FIELDS = ('id', 'fuente', 'id_origen', 'titulo', 'tipo_inmueble', 'tipo_operacion',
    'precio_usd', 'precio_soles', 'area_m2', 'area_terreno', 'area_construida',
    'distrito', 'latitud', 'longitud', 'precision_ubicacion', 'url',
    'estado_publicacion', 'ultima_vez_vista', 'fecha_retiro_confirmado',
    'descripcion', 'dormitorios', 'banos', 'estacionamientos')

def number(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Cruce de la descripción cruda contra los campos estructurados
# ═══════════════════════════════════════════════════════════════════════════
# La descripción trae datos en texto libre ("120 m2", "3 dormitorios", "S/ 350,000")
# que deben coincidir con las columnas. El cotejo es EXACTO: cualquier diferencia
# se marca para revisar. Solo se compara cuando ambos lados hablan de lo mismo,
# para no inventar conflictos (p. ej. un m² de terreno contra area_construida).

def _decimal(texto):
    """Decimal desde un número con separador de miles ('350,000' -> 350000)."""
    limpio = (texto or '').replace(',', '').strip()
    try:
        return Decimal(limpio)
    except (InvalidOperation, ValueError):
        return None


def _coinciden(texto, campo):
    """True si ambos lados existen y son iguales. Sin uno de los dos no hay conflicto."""
    if texto is None or campo is None:
        return True
    try:
        return Decimal(str(texto)) == Decimal(str(campo))
    except (InvalidOperation, ValueError):
        return True


def _entero_antes(descripcion, etiquetas):
    """Primer 'N etiqueta' de la descripción, como entero ('3 dormitorios' -> 3)."""
    texto = (descripcion or '').lower()
    for etiqueta in etiquetas:
        m = re.search(rf'(\d+)\s*{etiqueta}\b', texto)
        if m:
            return int(m.group(1))
    return None


def _unica_area(descripcion):
    """El m² suelto de la descripción solo si hay UNO (con dos o más es ambiguo)."""
    coincidencias = re.findall(r'(\d{1,5}(?:[.,]\d{1,2})?)\s*m(?:2|²)', descripcion or '', re.IGNORECASE)
    if len(coincidencias) != 1:
        return None
    return _decimal(coincidencias[0])


def _precios_de_texto(descripcion):
    """Precios explícitos con moneda en la descripción."""
    texto = descripcion or ''
    soles = usd = None
    m = re.search(r'S/\s*\.?\s*([\d][\d.,]*)', texto, re.IGNORECASE)
    if m:
        soles = _decimal(m.group(1))
    m = re.search(r'(?:US\$|USD)\s*([\d][\d.,]*)', texto, re.IGNORECASE)
    if m:
        usd = _decimal(m.group(1))
    return {'soles': soles, 'usd': usd}


def _monto(valor):
    return f'{valor:,.0f}'


def _alertas_descripcion(row):
    """Contradicciones entre la descripción cruda y los campos. Categoría 'review'."""
    descripcion = (row.get('descripcion') or '').strip()
    if not descripcion:
        return []
    alertas = []

    def flag(code, mensaje):
        alertas.append({'code': code, 'category': 'review', 'message': mensaje})

    # ── Área: primero por etiqueta explícita, si no por el único m² suelto ──
    terreno_texto = extraer_area_etiquetada(descripcion, ETIQUETAS_TERRENO)
    construida_texto = extraer_area_etiquetada(descripcion, ETIQUETAS_CONSTRUIDA)
    if terreno_texto is not None and not _coinciden(terreno_texto, row.get('area_terreno')):
        flag('descripcion_area_terreno_conflicto',
             f'La descripción dice {terreno_texto:g} m² de terreno y el campo dice {row["area_terreno"]:g}.')
    if construida_texto is not None and not _coinciden(construida_texto, row.get('area_construida')):
        flag('descripcion_area_construida_conflicto',
             f'La descripción dice {construida_texto:g} m² construidos y el campo dice {row["area_construida"]:g}.')
    if terreno_texto is None and construida_texto is None:
        area_texto = _unica_area(descripcion)
        if area_texto is not None and not _coinciden(area_texto, row.get('area_m2')):
            flag('descripcion_area_conflicto',
                 f'La descripción dice {area_texto:g} m² y el campo área dice {row["area_m2"]:g}.')

    # ── Ambientes: enteros, cualquier diferencia cuenta ──
    for etiquetas, campo, nombre in (
        (('dormitorios', 'dormitorio', 'habitaciones', 'habitación'), 'dormitorios', 'dormitorios'),
        (('baños', 'baño'), 'banos', 'baños'),
        (('cocheras', 'cochera', 'estacionamientos', 'estacionamiento', 'garajes', 'garaje'),
         'estacionamientos', 'cocheras'),
    ):
        n = _entero_antes(descripcion, etiquetas)
        if n is not None and row.get(campo) is not None and n != row[campo]:
            flag(f'descripcion_{campo}_conflicto',
                 f'La descripción dice {n} {nombre} y el campo dice {row[campo]}.')

    # ── Precio, solo con moneda explícita ──
    precios = _precios_de_texto(descripcion)
    if precios['usd'] is not None and not _coinciden(precios['usd'], row.get('precio_usd')):
        flag('descripcion_precio_usd_conflicto',
             f'La descripción dice US$ {_monto(precios["usd"])} y el campo dice US$ {_monto(row["precio_usd"])}.')
    if precios['soles'] is not None and not _coinciden(precios['soles'], row.get('precio_soles')):
        flag('descripcion_precio_soles_conflicto',
             f'La descripción dice S/ {_monto(precios["soles"])} y el campo dice S/ {_monto(row["precio_soles"])}.')

    # ── Tipo y operación: solo señales fuertes ──
    texto = descripcion.lower()
    operacion = None
    if re.search(r'\b(alquiler|alquilo|arriendo|se alquila)\b', texto):
        operacion = 'Alquiler'
    elif re.search(r'\b(vendo|se vende|en venta)\b', texto):
        operacion = 'Venta'
    if operacion and row.get('tipo_operacion') and row['tipo_operacion'] not in (operacion, 'Ambos', 'No especificado'):
        flag('descripcion_operacion_conflicto',
             f'La descripción sugiere {operacion} y el campo dice {row["tipo_operacion"]}.')

    tipo = None
    for patron, etiqueta in (
        (r'\b(departamento|depa|dpto|flat)\b', 'Departamento'),
        (r'\b(casa|chalet|villa)\b', 'Casa'),
        (r'\b(terreno|lote|parcela)\b', 'Terreno'),
        (r'\boficina\b', 'Oficina'),
        (r'\blocal\b', 'Local'),
    ):
        if re.search(patron, texto):
            tipo = etiqueta
            break
    if tipo and row.get('tipo_inmueble') and row['tipo_inmueble'] not in (tipo, 'Otro'):
        flag('descripcion_tipo_conflicto',
             f'La descripción sugiere {tipo} y el campo dice {row["tipo_inmueble"]}.')

    return alertas


def analyze(rows, ceiling=None):
    mapped = []
    result = []
    for index, source in enumerate(rows):
        row = dict(source)
        usd, pen = number(row.get('precio_usd')), number(row.get('precio_soles'))
        price = usd if usd and usd > 0 else pen / Decimal('3.44') if pen and pen > 0 else None
        ratios = {}
        if row.get('tipo_operacion') == 'Venta' and price:
            for field in ('area_m2', 'area_terreno', 'area_construida'):
                area = number(row.get(field))
                if area and area > 0: ratios[field] = price / area
        row.update(ratios=ratios, precio_comparable_usd=price, conversion_estimada=not bool(usd and usd > 0))
        result.append(row)
        mapped.append({'id': row.get('id', index), 'source_key': row.get('fuente'),
            'property_type': row.get('tipo_inmueble'), 'operation_type': row.get('tipo_operacion'),
            'district': row.get('distrito'), 'price': price, 'currency_symbol': '$',
            'land_area_m2': row.get('area_terreno'), 'built_area_m2': row.get('area_construida'),
            'lat': row.get('latitud'), 'lng': row.get('longitud'),
            'location_precision': row.get('precision_ubicacion'), 'url': row.get('url'),
            'quality_excluded': row.get('excluida',False), 'quality_exclusion_reason': row.get('motivo',''),
            'quality_stat_eligible': row.get('estado_publicacion') == 'activa',
            '_quality_input': {'legacy_area':bool(row.get('area_m2') and not row.get('area_terreno') and not row.get('area_construida'))}})
    annotate_map_quality(mapped)
    for row, quality in zip(result, mapped):
        row['alertas'] = [a['message'] for a in quality['quality_alerts']]
        row['quality_status'] = quality['quality_status']
    # Cruce descripción ↔ campos: se suma como alerta de revisión sin alterar las
    # reglas estadísticas. Un registro sin alertas previas pasa a 'review'.
    for row in result:
        descripcion_alertas = _alertas_descripcion(row)
        row['descripcion_conflicto'] = bool(descripcion_alertas)
        if descripcion_alertas:
            row['alertas'] = row['alertas'] + [a['message'] for a in descripcion_alertas]
            if row['quality_status'] == 'clear':
                row['quality_status'] = 'review'
    return result

def inspect_row(row, ceiling=None, exchange=None):
    return analyze([row])[0]
