"""Secondary estimate from references when the primary ACM cannot calculate."""
import math
from statistics import median

from .comparable_policy import land_only
from .listing_operation import resolve_operation


def reference_usable(row, area, excluded=()):
    """Shared eligibility for a secondary calculation after type/radius filtering."""
    from .components_engine import positive
    return (row['id'] not in excluded and bool(positive(row.get('price')))
            and bool(positive(row.get(area))) and resolve_operation(row)[0] == 'Venta'
            and row.get('operation_status') != 'review'
            and not row.get('review_excluded') and not row.get('duplicate_of'))


def calculate_from_references(records, params, excluded, primary):
    from .components_engine import positive

    target = 'Terreno' if land_only(params) else params.get('property_type', 'Casa')
    area = 'land' if target == 'Terreno' else 'built'
    references = sorted((row for row in records if row['kind'] == target and row['distance'] <= params['radius']),
                        key=lambda row: (row['distance'], str(row['id'])))[:5]
    if not references:
        return primary
    excluded = set(excluded)
    selected = [row for row in references if reference_usable(row, area, excluded)]
    result = {**primary, 'model': 'land' if area == 'land' else 'built',
              'reference_mode': True, 'reference_ids': [row['id'] for row in selected],
              'reference_display_ids': [row['id'] for row in references],
              'selection_method': 'reference_fallback', 'status': 'insufficient',
              'land_radius': params['radius'],
              'land_ids': [row['id'] for row in selected] if area == 'land' else [],
              'house_ids': [row['id'] for row in selected] if area == 'built' else [],
              'land_count': len(selected) if area == 'land' else 0,
              'house_count': len(selected) if area == 'built' else 0,
              'selection_count': len(selected), 'eligible_count': 0,
              'new': None, 'old': None, 'land_unit': None, 'breakdown': [],
              'messages': ['No se obtuvo un cálculo con comparables aptos. Se muestran hasta cinco referencias del mismo tipo, las más cercanas dentro del radio seleccionado.']}
    # A house's independent soil calculation remains useful even when its
    # construction cannot be estimated with suitable houses. Keep its evidence
    # without presenting the area-based fallback as a component calculation.
    if target == 'Casa':
        for key in ('land_unit', 'land_ids', 'land_count', 'land_radius', 'land_dispersion'):
            if key in primary:
                result[key] = primary[key]
        result['messages'] = list(primary.get('messages', [])) + result['messages']
    # A failed primary calculation may have component details; none of those
    # should masquerade as a decomposition in this separate area-based method.
    for key in ('built_unit_method', 'built_reference_id', 'recommended_ids', 'usable_house_count'):
        result.pop(key, None)
    if not selected:
        result['messages'].append('No hay referencias seleccionadas con precio y metraje válidos para calcular.')
        return result
    units = sorted(row['price'] / row[area] for row in selected)
    unit = median(units)
    target_area = params[area]
    total = unit * target_area
    result.update(status='ok',
                  old={'total': total, 'unit': unit, 'houses': len(selected)},
                  new={'total': total, 'unit': unit, 'area_basis': area,
                       'range_low': units[int((len(units) - 1) * .25)] * target_area,
                       'range_high': units[math.ceil((len(units) - 1) * .75)] * target_area,
                       'delta': 0, 'delta_pct': 0},
                  breakdown=[{'id': row['id'], 'method': result['model'], 'reference_used': True,
                              'offer_unit': row['price'] / row[area], 'area': row[area],
                              'adjusted_total': row['price'] / row[area] * target_area,
                              'usable': True} for row in selected])
    if area == 'land':
        result['land_unit'] = unit
    label = 'terreno' if area == 'land' else 'área construida'
    result['messages'].append(f'Cálculo con {len(selected)} referencias: mediana del precio por m² de {label} multiplicada por el área del inmueble. Revisa sus diferencias y justifica el valor adoptado.')
    return result
