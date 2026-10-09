"""Oficina Remax, separada del agente, para filtros del mapa."""
import json
import re


def remax_agency(raw, combined=None):
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            raw = {}
    office = raw.get('Oficina') if isinstance(raw, dict) else None
    if not office and re.match(r'^RE\s*/?\s*MAX\b', str(combined or ''), re.I):
        office = str(combined).split(' - ', 1)[0]
    return re.sub(r'\s+', ' ', str(office or '')).strip() or None
