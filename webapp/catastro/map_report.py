"""Public-report measurements for authenticated maps; never GIS area guesses.

Return only the measurements and report selectors, not owners or identifiers
from the other sections of the private archive. Multiple unit reports remain
separate; their construction areas are never added together.
"""
import json
import hashlib
import re
import unicodedata
from urllib.parse import urlsplit

from django.core.cache import cache

from .state import data_dir
from .storage import R2, StorageError
from . import report_snapshot
from scrapi.geollaqta_scraper import Source, GalleryLinks, PORTAL, pdf_pages


class ReportUnavailable(RuntimeError):
    pass


def _archived_reports(lot_id):
    try:
        path = data_dir() / lot_id[:6] / lot_id / 'datos.json'
        if path.is_file():
            data = json.loads(path.read_text(encoding='utf-8'))
        else:
            body, _ = R2(timeout=4).get('geollaqta/' + lot_id[:6] + '/' + lot_id + '/datos.json')
            data = json.loads(body)
        if data.get('lot_id') != lot_id or data.get('district_ubigeo') != lot_id[:6]:
            return None
        reports = [dict(r) for r in data.get('reports', [])
                   if r.get('type') in ('cadastral_report_pdf', 'individual_record_pdf')]
        artifacts = {a.get('filename'): a for a in data.get('artifacts', [])}
        for report in reports:
            original = artifacts.get(report.get('filename'), {})
            if original.get('sha256'):
                report['_archive_sha256'] = original['sha256']
        if any(a.get('type') == 'facade_image' for a in data.get('artifacts', [])):
            for report in reports:
                report['facade_url'] = f'/acm/catastro/lotes/{lot_id}/fachada/'
        if data.get('extraction_revision', 0) < 2:
            for report in reports:
                report.pop('pages', None)
        return reports or None
    except (StorageError, ValueError, OSError):
        return None


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


def report_cache_key(lot_id, record_id=None, *, report_only=False):
    return ('geollaqta-report-only-v1:' if report_only else 'geollaqta-report-v3:') + lot_id + ':' + (record_id or 'first')


def cached_report(lot_id, record_id=None, *, report_only=False):
    return cache.get(report_cache_key(lot_id, record_id, report_only=report_only))


def download(url):
    # Both maps use the same source headers, redirect policy and timeout.
    # Interactive reads have one attempt; an outage is never cached as success.
    return Source(timeout=6).get(url, retry=False)


def archived_pages(lot_id, document):
    """Re-read archived originals without requiring a new COFOPRI connection."""
    name, digest = document.get('filename'), document.get('_archive_sha256')
    if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]+\.pdf', name)
            or not re.fullmatch(r'[a-f0-9]{64}', str(digest or ''))):
        return None
    try:
        from .state import data_dir
        path = data_dir() / lot_id[:6] / lot_id / name
        body = path.read_bytes() if path.is_file() else R2(timeout=4).get('geollaqta/'+lot_id[:6]+'/'+lot_id+'/'+name)[0]
        if not body.lstrip().startswith(b'%PDF-') or hashlib.sha256(body).hexdigest() != digest:
            return None
        return pdf_pages(body)
    except (StorageError, OSError, ValueError, RuntimeError):
        return None


def report_pdf(lot_id, record_id=None):
    """Return the original report for the same verified lot/unit as the card."""
    result = report_measurements(lot_id, record_id, report_only=True)
    selected = result['selected_record_id']
    for document in _archived_reports(lot_id) or []:
        if document.get('type') != 'cadastral_report_pdf' or document.get('record_id') != selected:
            continue
        name, digest = document.get('filename', ''), document.get('_archive_sha256', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.pdf', name) or not re.fullmatch(r'[a-f0-9]{64}', digest):
            continue
        try:
            body = R2(timeout=5).get(f'geollaqta/{lot_id[:6]}/{lot_id}/{name}')[0]
            if body.lstrip().startswith(b'%PDF-') and hashlib.sha256(body).hexdigest() == digest:
                document_metrics(pdf_pages(body), lot_id)
                return body
        except (StorageError, OSError, ValueError, RuntimeError):
            continue
    body = report_snapshot.read(lot_id, selected, as_pdf=True)
    if body is not None:
        return body
    # The selected record was checked against this lot's available reports.
    body = download('https://catastro.cofopri.gob.pe/geollaqta/reportefichas/vistapdf/reporte.php?id=' + selected)
    if not body.lstrip().startswith(b'%PDF-'):
        raise ReportUnavailable('El servicio no devolvió un reporte PDF.')
    document_metrics(pdf_pages(body), lot_id)
    return body


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


def report_measurements(lot_id, record_id=None, *, reports=None, report_only=False):
    if not re.fullmatch(r'\d{14}', lot_id):
        raise ValueError('Código catastral no válido.')
    if record_id and not re.fullmatch(lot_id[:6] + r'\d{13}', record_id):
        raise ValueError('Reporte catastral no válido.')
    saved = cached_report(lot_id, record_id, report_only=report_only)
    if saved is not None:
        return saved
    discover = reports is None
    if reports is None:
        reports = _archived_reports(lot_id)
    if discover and (reports is None or (report_only and not any(r.get('type') == 'cadastral_report_pdf' for r in reports))):
        reports = report_snapshot.read(lot_id, record_id) or reports
    facade = None
    if reports is None or (discover and report_only and not any(r.get('type') == 'cadastral_report_pdf' for r in reports)):
        html = download(PORTAL + 'vistadetalle.php?id_lote=' + lot_id)
        parser = GalleryLinks(lot_id[:6])
        parser.feed(html.decode('utf-8', errors='replace'))
        reports = parser.documents
        facade = next(iter(parser.images), None)
    documents = [r for r in reports
                 if r.get('type') in (('cadastral_report_pdf',) if report_only else ('individual_record_pdf', 'cadastral_report_pdf'))
                 and re.fullmatch(lot_id[:6] + r'\d{13}', str(r.get('record_id', '')))]
    choices = sorted({(r['record_id'], r.get('form_number', '')) for r in documents})
    available_reports = sorted({r['record_id'] for r in documents if r['type'] == 'cadastral_report_pdf'})
    if not choices:
        raise ReportUnavailable('No hay un reporte catastral disponible para este lote.')
    selected = record_id or (available_reports[0] if available_reports else choices[0][0])
    def named(document):
        return any(page.get('named_fields') for page in document.get('pages', []))
    candidates = sorted((r for r in documents if r['record_id'] == selected),
                        key=lambda r: 0 if r['type'] == 'individual_record_pdf' and named(r)
                        else 1 if r['type'] == 'cadastral_report_pdf' else 2)
    if not candidates:
        raise ReportUnavailable('El reporte elegido no pertenece al lote.')
    metrics = {'land_area': None, 'built_area': None, 'floors': None, 'units': None,
               'boundaries': {side: None for side in ('frente', 'derecha', 'izquierda', 'fondo')}}
    verified = False
    for document in candidates:
        if verified and document['type'] == 'individual_record_pdf' and not named(document):
            # A remote/unmapped ficha must not hold a successfully read report.
            continue
        try:
            downloaded = None
            pages = document.get('pages')
            if pages is None:
                pages = archived_pages(lot_id, document)
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
                downloaded = body
            extracted = document_metrics(pages, lot_id)
            if downloaded is not None and document['type'] == 'cadastral_report_pdf':
                report_snapshot.save(lot_id, document, documents, downloaded)
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
    cache.set(report_cache_key(lot_id, record_id, report_only=report_only), result, 900)
    cache.set(report_cache_key(lot_id, selected, report_only=report_only), result, 900)
    return result
