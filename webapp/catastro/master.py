"""Shared cadastral provider contract and a strictly whitelisted lot summary.

Only approved sources belong here. Uploaded DWGs without confirmed CRS/layer
mapping do not contribute. Public geometry can travel directly to the browser;
private R2 credentials and complete cadastral documents always stay server-side.
"""
import hashlib
import json
import re
from urllib.parse import urlsplit

from django.core.cache import cache

from cuadrantizacion import geollaqta as geo
from .state import data_dir
from .storage import R2, StorageError
from .map_report import (document_metrics, ReportUnavailable, cached_report,
                         report_measurements, report_cache_key, download)


def validate_lot(lot_id):
    if not re.fullmatch(r'\d{14}', lot_id) or lot_id[:6] not in geo.DISTRICTS:
        raise ValueError('Código catastral no válido.')
    return lot_id


def configuration():
    from .master_layers import catalogue
    references = [{**source, 'geometry_url': '/acm/catastro/fuentes/' + source['id'] + '/radio/'}
                  for source in catalogue()['sources'] if source.get('transport') == 'master' and source['active']
                  and source.get('contributes', True)]
    for source in references:
        source['placement'] = {k: v for k, v in source['placement'].items() if k != 'blocks'}
    return {'revision': 5, 'scope': 'radius', 'batch_size': 500,
            'providers': [{'id': 'geollaqta', 'active': True, 'service_base': geo.SERVICE_BASE,
                           'districts': [{'ubigeo': d['ubigeo'], 'name': d['name']}
                                         for d in geo.DISTRICTS.values()],
                           # Retain source metadata for already-open map clients.
                           'boundaries': {'service_base': geo.CATALOG['district_source'].rsplit('/', 1)[0],
                                          'layer': 0, 'code_field': 'ID_DIST'},
                           'province_ubigeo': geo.CATALOG['province_ubigeo'], 'sector_layer': 13, 'lot_layer': 10}] + references}


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
    return download(url)


def _facade_url(url, lot_id):
    parsed = urlsplit(url)
    return (parsed.scheme == 'https' and parsed.netloc == 'catastro.cofopri.gob.pe'
            and not parsed.query and not parsed.fragment and re.fullmatch(
                r'/img_catastro/' + lot_id[:6] + r'/[A-Za-z0-9_.-]+\.(jpg|jpeg|png)', parsed.path, re.I))


def lot_summary(lot_id, record_id=None):
    validate_lot(lot_id)
    if record_id and not re.fullmatch(lot_id[:6] + r'\d{13}', record_id):
        raise ValueError('Reporte catastral no válido.')
    key = 'master-summary-v3:' + lot_id + ':' + (record_id or 'first')
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
    shared = cached_report(lot_id, record_id)
    # Reuse the report already verified by either map, even during a source outage.
    # An archived individual form still has precedence over report fields.
    if not documents and shared:
        documents = [{'type': 'cadastral_report_pdf', **r} for r in shared['reports']]
    live = []
    connection_failed = False
    # Prefer the verified archive; only the selected lot can trigger a live read.
    if not documents:
        try:
            from scrapi.geollaqta_scraper import GalleryLinks
            parser = GalleryLinks(lot_id[:6])
            parser.feed(_download(geo.PORTAL + 'reportefichas/vistadetalle.php?id_lote=' + lot_id).decode('utf8', errors='replace'))
            live = parser.documents
            if not facade:
                facade = next((url for url in parser.images if _facade_url(url, lot_id)), None)
        except (OSError, ValueError, RuntimeError):
            connection_failed = True
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
    def read(document):
        if document['type'] == 'cadastral_report_pdf':
            return report_measurements(lot_id, selected, reports=documents)['metrics']
        pages = document.get('pages')
        if pages is None:
            from scrapi.geollaqta_scraper import pdf_pages
            url = document.get('source_url', '')
            parsed = urlsplit(url)
            if (parsed.scheme != 'https' or parsed.netloc != 'catastro.cofopri.gob.pe'
                    or not re.fullmatch(r'/geollaqta/reportefichas/vistapdf/ficha[a-z0-9]{1,12}\.php', parsed.path)
                    or parsed.query != 'id=' + document['record_id'] or parsed.fragment):
                raise ReportUnavailable('Origen de ficha no válido.')
            body = _download(url)
            if not body.lstrip().startswith(b'%PDF-'):
                raise ReportUnavailable('COFOPRI no devolvió la ficha en PDF.')
            pages = pdf_pages(body)
        return document_metrics(pages, lot_id)

    # Merge only this unit's documents, with the individual form taking priority.
    for document in candidates:
        try:
            extracted = read(document)
            if document['type'] == 'cadastral_report_pdf' and not record_id:
                shared = cached_report(lot_id, selected)
                if shared:
                    cache.set(report_cache_key(lot_id), shared, 900)
            for field in ('land_area', 'built_area', 'floors', 'units'):
                if values[field] is None:
                    values[field] = extracted.get(field)
            for side in values['boundaries']:
                if values['boundaries'][side] is None:
                    values['boundaries'][side] = extracted['boundaries'][side]
            verified = True
        except ReportUnavailable:
            continue
        except (OSError, ValueError, RuntimeError):
            connection_failed = True
            continue
    result = {'lot_id': lot_id, 'metrics': values, 'verified': verified, 'facade_url': facade,
              'reports': [{'record_id': rid, 'form_number': number} for rid, number in choices],
              'selected_record_id': selected,
              'document_status': 'verified' if verified else 'unavailable' if connection_failed or documents else 'not_published'}
    if result['document_status'] != 'unavailable':
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
