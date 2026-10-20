"""Selección visible y ajuste manual, independientes del cálculo de comparables."""


def report_records(params, records, excluded=()):
    excluded = set(excluded)
    ids = params.get('report_ids')
    selected = set(ids) if ids is not None else None
    return [row for row in records if (row['id'] in selected if selected is not None
                                      else row['id'] not in excluded)]


def report_total(params, result):
    return params.get('manual_valuation', (result.get('new') or {}).get('total'))


def report_unit_price(params, result, default=None):
    """Use the final target value per m² without changing report headings."""
    if report_total(params, result) is None:
        return default
    from math import isfinite
    area_key = (result.get('new') or {}).get('area_basis')
    if area_key not in ('land', 'built'):
        area_key = 'land' if result.get('model') == 'land' or params.get('property_type') == 'Terreno' else 'built'
    try:
        area, total = float(params.get(area_key)), float(report_total(params, result))
    except (ValueError, TypeError):
        return None
    return total / area if isfinite(area) and area > 0 and isfinite(total) and total >= 0 else None


def report_values(params, result):
    total = report_total(params, result)
    return {'market_entry': total * 1.05, 'commercial': total,
            'immediate': total * .95}
