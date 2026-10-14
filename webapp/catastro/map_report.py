"""Public-report measurements for authenticated maps; never GIS area guesses.

Return only the measurements and report selectors, not owners or identifiers
from the other sections of the private archive. Multiple unit reports remain
separate; their construction areas are never added together.
"""
import json
import re

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
            body, _ = R2().get('geollaqta/' + lot_id[:6] + '/' + lot_id + '/datos.json')
            data = json.loads(body)
        if data.get('lot_id') != lot_id or data.get('district_ubigeo') != lot_id[:6]:
            return None
        return [r for r in data.get('reports', []) if r.get('type') == 'cadastral_report_pdf'] or None
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


def report_measurements(lot_id, record_id=None):
    reports = _archived_reports(lot_id)
    source = None
    if reports is None:
        source = Source()
        html = source.get(PORTAL + 'vistadetalle.php?id_lote=' + lot_id)
        parser = GalleryLinks(lot_id[:6])
        parser.feed(html.decode('utf-8', errors='replace'))
        reports = [r for r in parser.documents if r['type'] == 'cadastral_report_pdf']
    if not reports:
        raise ReportUnavailable('No hay un reporte catastral disponible para este lote.')
    selected = next((r for r in reports if r['record_id'] == record_id), None) if record_id else reports[0]
    if selected is None:
        raise ReportUnavailable('El reporte elegido no pertenece al lote.')
    pages = selected.get('pages')
    if pages is None:
        source = source or Source()
        body = source.get(selected['source_url'])
        if not body.lstrip().startswith(b'%PDF-'):
            raise ReportUnavailable('COFOPRI no devolvió el reporte en PDF.')
        pages = pdf_pages(body)
    return {'lot_id': lot_id, 'selected_record_id': selected['record_id'],
            'reports': [{'record_id': r['record_id'], 'form_number': r.get('form_number', '')} for r in reports],
            'metrics': measurements(pages, lot_id)}
