"""Shared cadastral provider contract and a strictly whitelisted lot summary.

Only approved sources belong here. Uploaded DWGs without confirmed CRS/layer
mapping do not contribute. Public geometry can travel directly to the browser;
private R2 credentials and complete cadastral documents always stay server-side.
"""
import hashlib
import json
import re
import unicodedata
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from django.core.cache import cache

from cuadrantizacion import geollaqta as geo
from .state import data_dir
from .storage import R2, StorageError, NoRedirect
from .map_report import measurements, ReportUnavailable


def validate_lot(lot_id):
    if not re.fullmatch(r'\d{14}', lot_id) or lot_id[:6] not in geo.DISTRICTS:
        raise ValueError('Código catastral no válido.')
    return lot_id


def configuration():
    return {'revision': 1, 'scope': 'block', 'max_lots': 1000,
            'providers': [{'id': 'geollaqta', 'active': True, 'service_base': geo.SERVICE_BASE,
                           'districts': [{'ubigeo': d['ubigeo'], 'name': d['name']}
                                         for d in geo.DISTRICTS.values()],
                           'block_layer': 11, 'lot_layer': 10}]}


def manifest(lot_id):
    validate_lot(lot_id)
    key = 'master-manifest-v1:' + lot_id
    saved = cache.get(key)
    if saved is not None:
        return saved or None
    path = data_dir() / lot_id[:6] / lot_id / 'datos.json'
    try:
        body = path.read_bytes() if path.is_file() else R2(timeout=4).get(
            f'geollaqta/{lot_id[:6]}/{lot_id}/datos.json')[0]
        value = json.loads(body)
        if value.get('lot_id') != lot_id or value.get('district_ubigeo') != lot_id[:6]:
            raise ValueError('Archive identity mismatch')
        cache.set(key, value, 300)
        return value
    except (StorageError, OSError, ValueError, TypeError):
        cache.set(key, {}, 30)
        return None


def _download(url):
    # URLs only come from the strict GalleryLinks parser, never client input.
    with build_opener(NoRedirect()).open(Request(url), timeout=4) as response:
        body = response.read(8_000_001)
    if len(body) > 8_000_000:
        raise ValueError('Cadastral document too large')
    return body


def _facade_url(url, lot_id):
    parsed = urlsplit(url)
    return (parsed.scheme == 'https' and parsed.netloc == 'catastro.cofopri.gob.pe'
            and not parsed.query and not parsed.fragment and re.fullmatch(
                r'/img_catastro/' + lot_id[:6] + r'/[A-Za-z0-9_.-]+\.(jpg|jpeg|png)', parsed.path, re.I))


def _number(fields, labels, maximum):
    def norm(text):
        return ''.join(c for c in unicodedata.normalize('NFKD', str(text).upper())
                       if not unicodedata.combining(c)).strip()
    values = {str(f.get('value')).strip() for f in fields
              if norm(f.get('original_label', f.get('label', ''))) in labels and f.get('value') is not None}
    if len(values) != 1:
        return None
    value = next(iter(values))
    return int(value) if re.fullmatch(r'\d+', value) and 0 <= int(value) <= maximum else None


def document_metrics(pages, lot_id):
    values = measurements(pages, lot_id)  # Verifies sector, block and lot identity.
    fields = [f for page in pages for f in page.get('named_fields', [])]
    values['floors'] = _number(fields, {'PISOS', 'NIVELES', 'NUMERO DE PISOS', 'NRO DE PISOS'}, 200)
    values['units'] = _number(fields, {'UNIDADES', 'NUMERO DE UNIDADES', 'NRO DE UNIDADES'}, 100000)
    return values


def lot_summary(lot_id, record_id=None):
    validate_lot(lot_id)
    if record_id and not re.fullmatch(lot_id[:6] + r'\d{13}', record_id):
        raise ValueError('Reporte catastral no válido.')
    key = 'master-summary-v1:' + lot_id + ':' + (record_id or 'first')
    saved = cache.get(key)
    if saved is not None:
        return saved
    archive = manifest(lot_id)
    documents = list((archive or {}).get('reports', []))
    if archive and archive.get('extraction_revision', 0) < 2:
        # Never reuse fields extracted before the report-column correction.
        documents = [{k: v for k, v in d.items() if k != 'pages'} for d in documents]
    facade = None
    if any(a.get('type') == 'facade_image' for a in (archive or {}).get('artifacts', [])):
        facade = f'/acm/catastro/lotes/{lot_id}/fachada/'
    live = []
    # Prefer the verified archive; only the selected lot can trigger a live read.
    if not documents or not facade:
        try:
            from scrapi.geollaqta_scraper import GalleryLinks
            parser = GalleryLinks(lot_id[:6])
            parser.feed(_download(geo.PORTAL + 'reportefichas/vistadetalle.php?id_lote=' + lot_id).decode('utf8', errors='replace'))
            live = parser.documents
            if not facade:
                facade = next((url for url in parser.images if _facade_url(url, lot_id)), None)
        except (OSError, ValueError, RuntimeError):
            pass
    known = {(d.get('record_id'), d.get('type')) for d in documents}
    documents.extend(d for d in live if (d.get('record_id'), d.get('type')) not in known)
    documents = [d for d in documents if d.get('type') in ('individual_record_pdf', 'cadastral_report_pdf')
                 and re.fullmatch(lot_id[:6] + r'\d{13}', str(d.get('record_id', '')))]
    choices = sorted({(d['record_id'], d.get('form_number', '')) for d in documents})
    selected = record_id or (choices[0][0] if choices else None)
    if record_id and not any(d['record_id'] == record_id for d in documents):
        raise ValueError('El reporte no pertenece al lote.')
    values = {'land_area': None, 'built_area': None, 'floors': None, 'units': None,
              'boundaries': {side: None for side in ('frente', 'derecha', 'izquierda', 'fondo')}}
    verified = False
    candidates = sorted((d for d in documents if d['record_id'] == selected),
                        key=lambda d: d['type'] != 'individual_record_pdf')
    for document in candidates:
        try:
            pages = document.get('pages')
            if pages is None:
                from scrapi.geollaqta_scraper import pdf_pages
                url = document.get('source_url', '')
                # Check even archived descriptors before requesting an external URL.
                parsed = urlsplit(url)
                if (parsed.scheme != 'https' or parsed.netloc != 'catastro.cofopri.gob.pe'
                        or not re.fullmatch(r'/geollaqta/reportefichas/vistapdf/(reporte|ficha[a-z0-9]{1,12})\.php', parsed.path)
                        or parsed.query != 'id=' + document['record_id']):
                    continue
                body = _download(url)
                if not body.lstrip().startswith(b'%PDF-'):
                    continue
                pages = pdf_pages(body)
            extracted = document_metrics(pages, lot_id)
            for field in ('land_area', 'built_area', 'floors', 'units'):
                if values[field] is None:
                    values[field] = extracted[field]
            for side in values['boundaries']:
                if values['boundaries'][side] is None:
                    values['boundaries'][side] = extracted['boundaries'][side]
            verified = True
        except (OSError, ValueError, RuntimeError, ReportUnavailable):
            continue
    result = {'lot_id': lot_id, 'metrics': values, 'verified': verified, 'facade_url': facade,
              'reports': [{'record_id': rid, 'form_number': number} for rid, number in choices],
              'selected_record_id': selected}
    cache.set(key, result, 300 if verified else 30)
    return result


def archived_facade(lot_id):
    value = manifest(lot_id)
    item = next((a for a in (value or {}).get('artifacts', []) if a.get('type') == 'facade_image'), None)
    if not item:
        raise ValueError('Fachada no disponible.')
    filename = item.get('filename', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.(jpg|jpeg|png)', filename, re.I):
        raise ValueError('Archivo no válido.')
    local = data_dir() / lot_id[:6] / lot_id / filename
    body = local.read_bytes() if local.is_file() else R2(timeout=5).get(f'geollaqta/{lot_id[:6]}/{lot_id}/{filename}')[0]
    if not item.get('sha256') or hashlib.sha256(body).hexdigest() != item['sha256']:
        raise ValueError('La fachada no coincide con el archivo verificado.')
    return body
