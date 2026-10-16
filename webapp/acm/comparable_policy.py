"""Explainable ordering, age evidence and conservative automatic groups."""
import math


def age_years(value):
    if value is None or isinstance(value, bool) or value == '':
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    return int(value) if math.isfinite(value) and 0 <= value <= 150 and value == int(value) else None


def land_only(params):
    age = age_years(params.get('age'))
    return params.get('property_type', 'Casa') == 'Casa' and age is not None and age > 40


def surface_similarity(value, target):
    if not value or not target or value <= 0 or target <= 0:
        return 0
    return 100 * min(value, target) / max(value, target)


def selection_metrics(row, params):
    target = params.get('property_type', 'Casa')
    land = surface_similarity(row.get('land'), params.get('land'))
    built = surface_similarity(row.get('built'), params.get('built'))
    surface = land if target == 'Terreno' or land_only(params) else (
        math.sqrt(land * built) if target == 'Casa' else built)
    proximity = 100 / (1 + max(0, row.get('distance') or 0) / 250)
    age, subject_age = age_years(row.get('age')), age_years(params.get('age'))
    delta = abs(age - subject_age) if age is not None and subject_age is not None else None
    age_similarity = 100 / (1 + delta / max(3, min(10, .2 * subject_age))) if delta is not None else None
    age_active = subject_age is not None and target != 'Terreno' and not land_only(params)
    score = .35 * proximity + .35 * (age_similarity or 0) + .30 * surface if age_active else proximity
    return {'selection_score': round(score, 4), 'surface_similarity': round(surface, 2),
            'age_similarity': round(age_similarity, 2) if age_similarity is not None else None,
            'age_difference': delta, 'proximity_similarity': round(proximity, 2)}


def priority(row, params):
    metrics = selection_metrics(row, params)
    subject_age = age_years(params.get('age'))
    # Actual premieres precede fallback ages, provided eligibility already passed.
    premiere = int(age_years(row.get('age')) != 0) if subject_age == 0 else 0
    if subject_age is None or params.get('property_type') == 'Terreno' or land_only(params):
        return (0, row.get('distance') or 0, -metrics['surface_similarity'], str(row['id']))
    return (premiere, -metrics['selection_score'], row.get('distance') or 0, str(row['id']))


def selection_pool(rows, params):
    ordered = sorted(rows, key=lambda row: priority(row, params))
    if params.get('age') == 0:
        premieres = [row for row in ordered if age_years(row.get('age')) == 0]
        if premieres:
            return premieres
    return ordered


def automatic_houses(rows, params, unit_by_id):
    ordered = selection_pool(rows, params)
    if not ordered:
        return []
    first = ordered[0]
    chosen = [first]
    # These are initial operational limits, not learned market coefficients.
    for row in ordered[1:]:
        if len(chosen) >= 3:
            break
        if row['distance'] > 200 or abs(row['distance'] - first['distance']) > 50:
            continue
        fields = ('land', 'built')
        if any(surface_similarity(row.get(key), params.get(key)) < 70 for key in fields):
            continue
        if any(surface_similarity(first.get(key), params.get(key)) < 70 for key in fields):
            continue
        if params.get('age') is not None and abs(selection_metrics(row, params)['selection_score'] -
                                                selection_metrics(first, params)['selection_score']) > 8:
            continue
        units = (unit_by_id[first['id']], unit_by_id[row['id']])
        if max(units) / min(units) > 2.5:
            continue
        chosen.append(row)
    return [row['id'] for row in chosen]


def age_messages(params, rows):
    age = age_years(params.get('age'))
    if age is None or params.get('property_type') == 'Terreno' or land_only(params):
        return []
    if not rows:
        return ['No hay comparables completos con antigüedad conocida y superficies similares. Revisa las referencias o deja la antigüedad vacía para priorizar distancia.']
    messages = ['Selección por cercanía (35%), antigüedad (35%) y áreas (30%): reglas iniciales de ordenación, sin depreciación monetaria por año.']
    if age == 0 and not any(age_years(row.get('age')) == 0 for row in rows):
        messages.append('No se encontraron estrenos aptos: se utilizan las menores antigüedades disponibles combinadas con cercanía y áreas.')
    if any(abs(age_years(row.get('age')) - age) > 10 for row in rows):
        messages.append('Hay diferencias de antigüedad superiores a 10 años. La comparación requiere revisión del agente.')
    return messages
