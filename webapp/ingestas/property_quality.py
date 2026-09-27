"""The quality dashboard and map share the same explainable alert rules."""
from decimal import Decimal, InvalidOperation
from cuadrantizacion.property_quality import annotate_map_quality

DATA_FIELDS = ('id', 'fuente', 'id_origen', 'titulo', 'tipo_inmueble', 'tipo_operacion',
    'precio_usd', 'precio_soles', 'area_m2', 'area_terreno', 'area_construida',
    'distrito', 'latitud', 'longitud', 'precision_ubicacion', 'url', 'estado_publicacion')

def number(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None

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
    return result

def inspect_row(row, ceiling=None, exchange=None):
    return analyze([row])[0]
