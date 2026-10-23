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


def d1_lot_summary(lot_id, record_id=None):
    """Return the linked Catastro Maestro record when D1 is the configured store."""
    from . import source_manager
    if not source_manager.durable():
        return None
    from .master_d1 import Gateway
    gateway = Gateway()
    rows = gateway.read(
        '''SELECT e.id AS entity_id,e.ubigeo,i.version_id,v.source_id,v.label AS version_label,
                  a.sector,a.block,a.lot,a.gis_land_area,a.gis_built_area,
                  a.floors AS lot_floors,a.units AS lot_units,a.address
           FROM identities i
           JOIN versions v ON v.id=i.version_id
           JOIN entities e ON e.id=i.entity_id
           LEFT JOIN current_attributes a ON a.entity_id=e.id
           WHERE i.layer='lote' AND i.source_feature_id=?
             AND v.source_id LIKE 'geollaqta-%'
           ORDER BY v.created_at DESC LIMIT 1''', [lot_id])
    if not rows:
        return None
    row = rows[0]
    entity_id = row['entity_id']
    unit_rows = gateway.read(
        '''SELECT DISTINCT i.entity_id AS entity_id,i.source_feature_id,i.layer
           FROM relationships r JOIN identities i ON i.entity_id=r.entity_id
           WHERE r.related_entity_id=?
             AND r.kind IN ('unidad_en_lote','documento_de_lote')
             AND i.layer IN ('unidad','registro_documental')
           ORDER BY source_feature_id''', [entity_id])
    choices = [str(item['source_feature_id']) for item in unit_rows]
    if record_id and record_id not in choices:
        raise ValueError('El reporte no pertenece al lote vinculado.')
    selected = record_id or (choices[0] if choices else None)
    unit = next((item for item in unit_rows
                 if str(item['source_feature_id']) == selected), None)
    unit_attributes = gateway.read(
        '''SELECT * FROM current_attributes WHERE entity_id=?''',
        [unit['entity_id']]) if unit else []
    unit_row = unit_attributes[0] if unit_attributes else {}
    media_entities = [entity_id, *[item['entity_id'] for item in unit_rows]]
    media = gateway.read(
        '''SELECT id,kind,object_key,sha256,observed_at,source_version,details_json
           FROM media WHERE entity_id IN (SELECT value FROM json_each(?))
           ORDER BY kind,id''', [json.dumps(list(dict.fromkeys(media_entities)))])
    facade = next((item for item in media
                   if 'facade' in str(item.get('kind', '')).lower()), None)
    def media_record(item):
        try:
            return json.loads(item.get('details_json') or '{}').get('source_record_id')
        except (TypeError, ValueError):
            return None
    pdf_candidates = [item for item in media
                      if str(item.get('kind', '')).lower().endswith('pdf')
                      or 'report' in str(item.get('kind', '')).lower()]
    pdf = next((item for item in pdf_candidates
                if media_record(item) == selected), pdf_candidates[0] if pdf_candidates else None)
    metric = lambda value: None if value is None else str(value)
    values = {
        'land_area': metric(unit_row.get('land_area')),
        'built_area': metric(unit_row.get('built_area')),
        'floors': metric(unit_row.get('floors') if unit_row.get('floors') is not None
                         else row.get('lot_floors')),
        'units': metric(unit_row.get('units') if unit_row.get('units') is not None
                        else row.get('lot_units')),
        'perimeter': metric(unit_row.get('perimeter')),
        'boundaries': {
            'frente': metric(unit_row.get('front')), 'derecha': metric(unit_row.get('right')),
            'izquierda': metric(unit_row.get('left')), 'fondo': metric(unit_row.get('back')),
        },
    }
    return {
        'lot_id': lot_id,
        'metrics': values,
        'gis_metrics': {
            'land_area': metric(row.get('gis_land_area')),
            'built_area': metric(row.get('gis_built_area')),
            'floors': metric(row.get('floors')),
            'units': metric(row.get('units')),
        },
        'verified': any(value not in (None, '') for value in values.values()
                        if not isinstance(value, dict)),
        'facade_url': '/acm/catastro/medios/' + facade['id'] + '/' if facade else None,
        'reports': [{'record_id': value, 'form_number': ''} for value in choices],
        'selected_record_id': selected,
        'report_pdf_url': ('/acm/catastro/medios/' + pdf['id'] + '/'
                           if pdf else None),
        'document_status': 'verified' if values['built_area'] or values['land_area'] else 'available',
        'source_label': 'Catastro Maestro · D1',
        'master': {
            'entity_id': entity_id,
            'source_version_id': row.get('version_id'),
            'source_id': row.get('source_id'),
            'source_feature_id': lot_id,
            'selected_entity_id': unit.get('entity_id') if unit else entity_id,
            'location': {'sector': row.get('sector'), 'block': row.get('block'),
                         'lot': row.get('lot'), 'address': row.get('address')},
        },
    }


def merge_d1_summary(base, master_record):
    """Prefer normalized master values while retaining verified source evidence."""
    if not master_record:
        return base
    result = {**(base or {}), **master_record}
    base_metrics = (base or {}).get('metrics') or {}
    metrics = dict(master_record.get('metrics') or {})
    for key, value in metrics.items():
        if isinstance(value, dict):
            merged = dict(base_metrics.get(key) or {})
            merged.update({side: item for side, item in value.items() if item not in (None, '')})
            metrics[key] = merged
        elif value in (None, ''):
            metrics[key] = base_metrics.get(key)
    result['metrics'] = metrics
    reports = {}
    for item in [*((base or {}).get('reports') or []), *(master_record.get('reports') or [])]:
        previous = reports.get(item['record_id'], {})
        reports[item['record_id']] = {
            **previous, **item,
            'form_number': item.get('form_number') or previous.get('form_number'),
        }
    result['reports'] = list(reports.values())
    result['selected_record_id'] = (master_record.get('selected_record_id') or
                                    (base or {}).get('selected_record_id'))
    result['facade_url'] = master_record.get('facade_url') or (base or {}).get('facade_url')
    result['verified'] = bool((base or {}).get('verified') or master_record.get('verified'))
    return result


def configuration():
    from .master_layers import catalogue
    references = [{**source, 'geometry_url': '/acm/catastro/fuentes/' + source['id'] + '/radio/'}
                  for source in catalogue()['sources'] if source.get('transport') == 'master' and source['active']
                  and (source.get('contributes', True) or source.get('id') in
                       ('cayma-pud-2006-eu03', 'cayma-sector-32-provisional'))]
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
