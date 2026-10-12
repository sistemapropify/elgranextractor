"""Agent adjustments relative to the calculated ACM, not observed sale errors."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _amount(value):
    try:
        number = Decimal(str(value))
        if number.is_finite() and number >= 0:
            return number.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        pass
    return None


def valuation_comparison(params, result):
    calculated = _amount((result.get('new') or {}).get('total'))
    agent = _amount(params.get('manual_valuation'))
    difference = agent - calculated if agent is not None and calculated is not None else None
    variation = difference / calculated * 100 if difference is not None and calculated > 0 else None
    return {
        'metric_version': 1,
        'calculated_total': float(calculated) if calculated is not None else None,
        'agent_total': float(agent) if agent is not None else None,
        'manually_adjusted': agent is not None,
        'adjustment_amount': float(difference) if difference is not None else None,
        'variation_pct': float(variation) if variation is not None else None,
        'absolute_variation_pct': float(abs(variation)) if variation is not None else None,
    }


def history_comparison(history):
    if history.metodo != 'componentes':
        return {'calculated_total': None, 'agent_total': None, 'variation_pct': None,
                'absolute_variation_pct': None, 'manually_adjusted': False}
    # Older history already retained both inputs. Derive its metrics without
    # changing the original snapshot or assuming untouched values were reviewed.
    return valuation_comparison(history.parametros_json or {}, history.resultado_json or {})


def adjustment_kpis(comparisons):
    available = [item for item in comparisons if item['calculated_total'] is not None]
    reviewed = [item for item in available if item['manually_adjusted'] and item['variation_pct'] is not None]
    count = len(reviewed)
    return {
        'available_count': len(available), 'reviewed_count': count,
        'mean_absolute_variation': sum(item['absolute_variation_pct'] for item in reviewed) / count if count else None,
        'mean_signed_variation': sum(item['variation_pct'] for item in reviewed) / count if count else None,
        'within_ten_pct': 100 * sum(item['absolute_variation_pct'] <= 10 for item in reviewed) / count if count else None,
    }
