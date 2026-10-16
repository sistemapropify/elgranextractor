"""Public-report measurements for authenticated maps; never GIS area guesses.

Return only the measurements and report selectors, not owners or identifiers
from the other sections of the private archive. Multiple unit reports remain
separate; their construction areas are never added together.
"""
import json
import re
import unicodedata
from urllib.parse import urlsplit

from django.core.cache import cache

from .state import State
from .storage import R2, StorageError
from scrapi.geollaqta_scraper import Source, GalleryLinks, PORTAL, pdf_pages


class ReportUnavailable(RuntimeError):
    pass


def _archived_reports(lot_id):
    state = State()
    try:
        path = state.root / lot_id[:6] / lot_id / 'datos.json'
        if path.is_file():
            data = json.loads(path.read_text(encoding='utf-8'))
        else:
            body, _ = R2(timeout=4).get('geollaqta/' + lot_id[:6] + '/' + lot_id + '/datos.json')
            data = json.loads(body)
        if data.get('lot_id') != lot_id or data.get('district_ubigeo') != lot_id[:6]:
            return None
        reports = [dict(r) for r in data.get('reports', []) if r.get('type') == 'cadastral_report_pdf']
        if data.get('extraction_revision', 0) < 2:
            for report in reports:
                report.pop('pages', None)
        return reports or None
    except (StorageError, ValueError, OSError):
        return None
    finally:
        state.close()


def measurements(pages, lot_id):
    fields = [f for p in pages for f in p.get('named_fields', [])]
    if not fields:
        raise ReportUnavailable('No se pudieron leer las medidas del reporte.')
    identity = {'SECT': lot_id[6:8], 'MZA': lot_id[8:11], 'LOTE': lot_id[11:14]}
    for label, expected in identity.items():
        values = [f.get('value') for f in fields if f.get('original_label') == label and f.get('section') == 'Ubicación geográfica']
        if len(lot_id) == 14 and (len(values) != 1 or str(values[0]).zfill(len(expected)) != expected):
            raise ReportUnavailable('El reporte no corresponde al lote seleccionado.')

    def value(predicate):
        matches = [f for f in fields if predicate(f)]
        if len(matches) != 1:
            return None
        raw = matches[0].get('value')
        if raw is None:
            return None
        raw = str(raw).strip()
        # Keep the report's exact decimal representation, including a comma.
        return raw if re.fullmatch(r'\d+(?:[.,]\d+)?', raw) else None

    return {
        'land_area': value(lambda f: f.get('original_label') == 'AREA LOTE (M2)'),
        'built_area': value(lambda f: f.get('original_label') == 'AREA CONSTRUIDA (M2)'),
        'boundaries': {side.lower(): value(lambda f, side=side: f.get('original_label') == side and
                                         f.get('label', '').startswith('Medida perimétrica'))
                       for side in ('FRENTE', 'DERECHA', 'IZQUIERDA', 'FONDO')},
    }


def report_cache_key(lot_id, record_id=None):
    return 'geollaqta-report-v2:' + lot_id + ':' + (record_id or 'first')


def cached_report(lot_id, record_id=None):
    return cache.get(report_cache_key(lot_id, record_id))


def download(url):
    # Both maps use the same source headers, redirect policy and timeout.
    # Interactive reads have one attempt; an outage is never cached as success.
    return Source().get(url, retry=False)


def document_metrics(pages, lot_id):
    result = measurements(pages, lot_id)
    fields = [f for page in pages for f in page.get('named_fields', [])]

    def number(labels, maximum):
        def norm(text):
            return ''.join(c for c in unicodedata.normalize('NFKD', str(text).upper())
                           if not unicodedata.combining(c)).strip()
        values = {str(f.get('value')).strip() for f in fields
                  if norm(f.get('original_label', f.get('label', ''))) in labels
                  and f.get('value') is not None}
        if len(values) != 1:
            return None
        value = next(iter(values))
        return int(value) if re.fullmatch(r'\d+', value) and 0 <= int(value) <= maximum else None

    result['floors'] = number({'PISOS', 'NIVELES', 'NUMERO DE PISOS', 'NRO DE PISOS'}, 200)
    result['units'] = number({'UNIDADES', 'NUMERO DE UNIDADES', 'NRO DE UNIDADES'}, 100000)
    return result


def report_measurements(lot_id, record_id=None, *, reports=None):
    if not re.fullmatch(r'\d{14}', lot_id):
        raise ValueError('Código catastral no válido.')
    if record_id and not re.fullmatch(lot_id[:6] + r'\d{13}', record_id):
        raise ValueError('Reporte catastral no válido.')
    saved = cached_report(lot_id, record_id)
    if saved is not None:
        return saved
    if reports is None:
        reports = _archived_reports(lot_id)
    if reports is None:
        html = download(PORTAL + 'vistadetalle.php?id_lote=' + lot_id)
        parser = GalleryLinks(lot_id[:6])
        parser.feed(html.decode('utf-8', errors='replace'))
        reports = parser.documents
    reports = [r for r in reports if r.get('type') == 'cadastral_report_pdf'
               and re.fullmatch(lot_id[:6] + r'\d{13}', str(r.get('record_id', '')))]
    reports = sorted(reports, key=lambda r: (r['record_id'], r.get('form_number', '')))
    if not reports:
        raise ReportUnavailable('No hay un reporte catastral disponible para este lote.')
    selected = next((r for r in reports if r['record_id'] == record_id), None) if record_id else reports[0]
    if selected is None:
        raise ReportUnavailable('El reporte elegido no pertenece al lote.')
    pages = selected.get('pages')
    if pages is None:
        url = selected.get('source_url', '')
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'catastro.cofopri.gob.pe'
                or parsed.path != '/geollaqta/reportefichas/vistapdf/reporte.php'
                or parsed.query != 'id=' + selected['record_id'] or parsed.fragment):
            raise ReportUnavailable('Origen de reporte no válido.')
        body = download(url)
        if not body.lstrip().startswith(b'%PDF-'):
            raise ReportUnavailable('COFOPRI no devolvió el reporte en PDF.')
        pages = pdf_pages(body)
    result = {'lot_id': lot_id, 'selected_record_id': selected['record_id'],
              'reports': [{'record_id': r['record_id'], 'form_number': r.get('form_number', '')} for r in reports],
              'metrics': document_metrics(pages, lot_id)}
    # One validated result serves ACM and Cuadrantización, including unit selection.
    cache.set(report_cache_key(lot_id, record_id), result, 900)
    cache.set(report_cache_key(lot_id, selected['record_id']), result, 900)
    return result
