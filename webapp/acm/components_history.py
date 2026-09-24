"""Persistencia reproducible del ACM por componentes en el historial existente."""
import hashlib
import json
from decimal import Decimal
from statistics import median

from django.db import transaction

from .models import ACMLink, generar_codigo_acm


def _decimal(value):
    return Decimal(str(round(float(value or 0), 2)))


def _reference_summary(records, result, excluded):
    selected = set(result.get('land_ids', ())) | set(result.get('house_ids', ()))
    excluded = set(excluded)
    reasons = {}
    count = 0
    for row in records:
        if row['id'] in selected and row['id'] not in excluded:
            continue
        count += 1
        row_reasons = ['Desmarcada manualmente'] if row['id'] in excluded else (row.get('issues') or ['Fuera del grupo utilizado'])
        for reason in row_reasons:
            reasons[reason] = reasons.get(reason, 0) + 1
    return {'count': count, 'reasons': reasons}


def _unit_values(result):
    if result.get('model') == 'components':
        return [row['built_unit'] for row in result.get('breakdown', ()) if row.get('usable')]
    return [row['offer_unit'] for row in result.get('breakdown', ()) if row.get('usable')]


def persist_component_history(user, params, records, result, excluded=()):
    """Guarda una selección calculada y evita duplicarla al descargar el Word."""
    if not result.get('new'):
        raise ValueError('El análisis todavía no tiene un resultado calculado para guardar.')
    excluded = sorted(set(excluded))
    selected_ids = set(result.get('land_ids', ())) | set(result.get('house_ids', ()))
    selected_records = [row for row in records if row['id'] in selected_ids and row['id'] not in excluded]
    stored_result = dict(result)
    stored_result['excluded_ids'] = excluded
    stored_result['reference_summary'] = _reference_summary(records, result, excluded)
    fingerprint_payload = {
        'version': result.get('version'), 'params': params,
        'selected': sorted(row['id'] for row in selected_records), 'excluded': excluded,
        'total': result['new'].get('total'),
    }
    fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    units = _unit_values(result) or [result['new'].get('unit') or result['new'].get('built_unit') or 0]
    units = [float(value) for value in units if value is not None]
    unit_mid = median(units) if units else 0
    area = params.get('land') if params['property_type'] == 'Terreno' else params.get('built')
    total = result['new']['total']
    defaults = {
        'codigo': generar_codigo_acm(), 'origen': 'componentes', 'metodo': 'componentes',
        'tipo_propiedad': params['property_type'], 'area_m2': _decimal(area),
        'es_terreno': params['property_type'] == 'Terreno',
        'precio_min_m2': _decimal(min(units) if units else 0),
        'precio_max_m2': _decimal(max(units) if units else 0),
        'precio_promedio_m2': _decimal(sum(units) / len(units) if units else 0),
        'precio_promedio_ponderado_m2': _decimal(unit_mid),
        'valor_comercial': _decimal(total), 'precio_venta_sugerido': _decimal(total),
        'valor_realizacion': _decimal(total), 'num_comparables': len(selected_records),
        'propiedades_json': selected_records, 'parametros_json': params,
        'resultado_json': stored_result,
    }
    with transaction.atomic():
        existing = ACMLink.objects.filter(user=user, metodo='componentes', selection_fingerprint=fingerprint).first()
        if existing:
            return existing, False
        return ACMLink.objects.create(user=user, selection_fingerprint=fingerprint, **defaults), True
