"""Resolve listing operation from explicit evidence, never from its price."""
import re
import unicodedata
from urllib.parse import unquote, urlsplit

POLICY_VERSION = 'listing-operation-1'


def operation_text(value):
    text = ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').casefold())
                   if not unicodedata.combining(c))
    rent = bool(re.search(r'\b(?:alquiler(?:es)?|alquilo|alquila|alquilar|arriendo|arrendamiento|renta|rent|rental)\b|/alcl', text))
    sale = bool(re.search(r'\b(?:venta|vendo|vende|vender|sale)\b|/vecl', text))
    if rent and sale or text.strip() == 'ambos':
        return 'Ambos'
    if rent:
        return 'Alquiler'
    if sale:
        return 'Venta'
    if re.search(r'\banticresis\b', text):
        return 'Anticresis'
    return None


def resolve_operation(record):
    original = record.get('_operation_title') or record.get('_operation_title_lower')
    # An imported display title can be synthetic (e.g. "Departamento en Venta").
    # Prefer the original title kept with the scraped listing.
    title = original if original else record.get('title')
    path = unquote(urlsplit(str(record.get('url') or '')).path).replace('-', ' ')
    evidence = {op for op in (operation_text(title), operation_text(path)) if op}
    if len(evidence) > 1:
        return 'No especificado', 'review'
    if evidence:
        return evidence.pop(), 'confirmed'
    declared = operation_text(record.get('operation'))
    return (declared, 'declared') if declared else ('No especificado', 'unknown')
