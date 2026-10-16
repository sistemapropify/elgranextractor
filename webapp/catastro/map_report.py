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
        reports = [dict(r) for r in data.get('reports', [])
                   if r.get('type') in ('cadastral_report_pdf', 'individual_record_pdf')]
        if any(a.get('type') == 'facade_image' for a in data.get('artifacts', [])):
            for report in reports:
                report['facade_url'] = f'/acm/catastro/lotes/{lot_id}/fachada/'
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
    return 'geollaqta-report-v3:' + lot_id + ':' + (record_id or 'first')


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
    facade = None
    if reports is None:
        html = download(PORTAL + 'vistadetalle.php?id_lote=' + lot_id)
        parser = GalleryLinks(lot_id[:6])
        parser.feed(html.decode('utf-8', errors='replace'))
        reports = parser.documents
        facade = next(iter(parser.images), None)
    documents = [r for r in reports
                 if r.get('type') in ('individual_record_pdf', 'cadastral_report_pdf')
                 and re.fullmatch(lot_id[:6] + r'\d{13}', str(r.get('record_id', '')))]
    choices = sorted({(r['record_id'], r.get('form_number', '')) for r in documents})
    available_reports = sorted({r['record_id'] for r in documents if r['type'] == 'cadastral_report_pdf'})
    if not choices:
        raise ReportUnavailable('No hay un reporte catastral disponible para este lote.')
    selected = record_id or (available_reports[0] if available_reports else choices[0][0])
    candidates = sorted((r for r in documents if r['record_id'] == selected),
                        key=lambda r: r['type'] != 'individual_record_pdf')
    if not candidates:
        raise ReportUnavailable('El reporte elegido no pertenece al lote.')
    metrics = {'land_area': None, 'built_area': None, 'floors': None, 'units': None,
               'boundaries': {side: None for side in ('frente', 'derecha', 'izquierda', 'fondo')}}
    verified = False
    for document in candidates:
        try:
            pages = document.get('pages')
            if pages is None:
                url = document.get('source_url', '')
                parsed = urlsplit(url)
                path = (r'/geollaqta/reportefichas/vistapdf/reporte\.php' if document['type'] == 'cadastral_report_pdf'
                        else r'/geollaqta/reportefichas/vistapdf/ficha[a-z0-9]{1,12}\.php')
                if (parsed.scheme != 'https' or parsed.netloc != 'catastro.cofopri.gob.pe'
                        or not re.fullmatch(path, parsed.path)
                        or parsed.query != 'id=' + selected or parsed.fragment):
                    continue
                body = download(url)
                if not body.lstrip().startswith(b'%PDF-'):
                    continue
                pages = pdf_pages(body)
            extracted = document_metrics(pages, lot_id)
            for field in ('land_area', 'built_area', 'floors', 'units'):
                if metrics[field] is None:
                    metrics[field] = extracted[field]
            for side in metrics['boundaries']:
                if metrics['boundaries'][side] is None:
                    metrics['boundaries'][side] = extracted['boundaries'][side]
            facade = document.get('facade_url') or facade
            verified = True
        except (ReportUnavailable, OSError, ValueError, RuntimeError):
            continue
    if not verified:
        raise ReportUnavailable('No se pudo leer el documento catastral del lote.')
    result = {'lot_id': lot_id, 'selected_record_id': selected,
              'reports': [{'record_id': rid, 'form_number': number} for rid, number in choices],
              'metrics': metrics, 'facade_url': facade}
    # One validated result serves both HTTP endpoints and keeps units separate.
    cache.set(report_cache_key(lot_id, record_id), result, 900)
    cache.set(report_cache_key(lot_id, selected), result, 900)
    return result
