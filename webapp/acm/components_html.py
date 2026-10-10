"""Informe HTML autónomo con la selección y valoración actuales del ACM."""
from urllib.parse import urlsplit

from django.template.loader import render_to_string
from django.utils import timezone

from .report_selection import report_records, report_total, report_values


def _number(value, suffix=''):
    return 'Sin informar' if value is None else f'{float(value):,.2f}{suffix}'


def _money(value):
    return 'Sin informar' if value is None else f'USD {float(value):,.2f}'


def _link(value):
    value = str(value or '')
    parsed = urlsplit(value)
    return value if parsed.scheme in ('http', 'https') and parsed.netloc else ''


def build_acm_html(params, records, result, excluded=(), generated_at=None):
    selected = report_records(params, records, excluded)
    details = {detail['id']: detail for detail in result['breakdown']}
    rows = []
    for record in selected:
        detail = details.get(record['id'], {})
        if result['model'] == 'components' and detail:
            operation = (
                f"{_money(record['price'])} + ajuste por terreno "
                f"({_money(detail.get('land_adjustment'))}) + ajuste por construcción "
                f"({_money(detail.get('built_adjustment'))}) = "
                f"{_money(detail.get('target_estimate'))}. "
                f"Peso aplicado: {_number(detail.get('similarity_weight'), '%')}."
            )
        elif detail:
            area_key = 'land' if record['kind'] == 'Terreno' else 'built'
            operation = (
                f"{_money(record['price'])} / {_number(record.get(area_key), ' m²')} "
                f"× {_number(params.get(area_key), ' m²')} = "
                f"{_money(detail.get('adjusted_total'))}."
            )
        else:
            operation = 'Sin desglose individual disponible.'
        rows.append({
            'title': record.get('title') or record['kind'],
            'district': record.get('district') or 'Sin informar',
            'kind': record['kind'], 'price': _money(record.get('price')),
            'land': _number(record.get('land'), ' m²'),
            'built': _number(record.get('built'), ' m²'),
            'distance': _number(record.get('distance'), ' m'),
            'url': _link(record.get('url')), 'operation': operation,
        })
    generated_at = generated_at or timezone.localtime(timezone.now())
    values = {key: _money(value) for key, value in report_values(params, result).items()}
    new = result.get('new') or {}
    if result['model'] == 'components':
        method = 'Suelo + construcción y mejoras'
        calculation = (
            f"Terreno: {_number(params.get('land'), ' m²')} × "
            f"{_money(result.get('land_unit'))}/m² = {_money(new.get('land_value'))}. "
            f"Construcción y mejoras: {_money(new.get('built_value'))}. "
            f"Total calculado: {_money(new.get('total'))}."
        )
    else:
        area_key = new.get('area_basis', 'land' if result['model'] == 'land' else 'built')
        method = 'Mediana del precio por m² de los comparables'
        calculation = (
            f"{_money(new.get('unit'))}/m² × {_number(params.get(area_key), ' m²')} "
            f"= {_money(new.get('total'))}."
        )
    return render_to_string('acm/components_report.html', {
        'property_type': params.get('property_type', 'Casa'),
        'generated_at': generated_at.strftime('%d/%m/%Y %H:%M'),
        'land': _number(params.get('land'), ' m²'),
        'built': _number(params.get('built'), ' m²'),
        'radius': _number(params.get('radius'), ' m'),
        'lat': params.get('lat'), 'lng': params.get('lng'),
        'rows': rows, 'values': values, 'method': method, 'calculation': calculation,
        'manual_value': _money(report_total(params, result)) if 'manual_valuation' in params else None,
        'messages': result.get('messages', []),
    })
