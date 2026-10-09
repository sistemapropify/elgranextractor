"""Selección visible y ajuste manual, independientes del cálculo de comparables."""


def report_records(params, records, excluded=()):
    excluded = set(excluded)
    ids = params.get('report_ids')
    selected = set(ids) if ids is not None else None
    return [row for row in records if (row['id'] in selected if selected is not None
                                      else row['id'] not in excluded)]


def report_total(params, result):
    return params.get('manual_valuation', (result.get('new') or {}).get('total'))
