"""Verified report copies shared by map readers, separate from collector progress.

Only the original report PDF and its source/identity metadata are mirrored. This
does not mark a lot collected or replace the collector's complete datos.json.
"""
import hashlib
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .state import data_dir
from .storage import R2, StorageError

logger = logging.getLogger(__name__)
FAILURES = (StorageError, OSError, ValueError, TypeError, KeyError)


def _prefix(lot_id):
    if not re.fullmatch(r'\d{14}', lot_id):
        raise ValueError('Código catastral no válido.')
    return f'geollaqta/{lot_id[:6]}/{lot_id}/map-reports/'


def _documents(lot_id, documents):
    result = {}
    if not isinstance(documents, list):
        return []
    for document in documents:
        if not isinstance(document, dict):
            continue
        record = document.get('record_id', '')
        if (document.get('type') != 'cadastral_report_pdf'
                or not isinstance(record, str)
                or not re.fullmatch(lot_id[:6] + r'\d{13}', record)):
            continue
        url = 'https://catastro.cofopri.gob.pe/geollaqta/reportefichas/vistapdf/reporte.php?id=' + record
        if document.get('source_url') != url:
            continue
        result[record] = {'type': 'cadastral_report_pdf', 'record_id': record,
                          'form_number': str(document.get('form_number', ''))[:100], 'source_url': url}
    return [result[key] for key in sorted(result)]


def _atomic(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            name = handle.name
            handle.write(body)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def _get(lot_id, name, cloud):
    path = data_dir() / lot_id[:6] / lot_id / 'map-reports' / name
    return path.read_bytes() if path.is_file() else cloud.get(_prefix(lot_id) + name)[0]


def read(lot_id, record_id=None):
    """Return report candidates with the selected PDF freshly parsed and checked."""
    try:
        _prefix(lot_id)
        # Defer credentials/network until a local copy is actually missing.
        class Remote:
            def get(self, key):
                return R2(timeout=3).get(key)
        cloud = Remote()
        index = json.loads(_get(lot_id, 'index.json', cloud))
        if not isinstance(index, dict) or index.get('schema') != 1 or index.get('lot_id') != lot_id:
            return None
        documents = _documents(lot_id, index.get('reports', []))
        selected = record_id or (documents[0]['record_id'] if documents else None)
        document = next((d for d in documents if d['record_id'] == selected), None)
        if not document:
            return None
        metadata = json.loads(_get(lot_id, selected + '.json', cloud))
        if not isinstance(metadata, dict):
            return None
        digest = metadata.get('sha256', '')
        if (metadata.get('schema') != 1 or metadata.get('lot_id') != lot_id
                or metadata.get('record_id') != selected
                or metadata.get('source_url') != document['source_url']
                or not re.fullmatch(r'[a-f0-9]{64}', str(digest))):
            return None
        # Immutable original, never a filename supplied by a web request.
        name = 'reporte-' + selected + '-' + digest + '.pdf'
        body = _get(lot_id, name, cloud)
        if not body.lstrip().startswith(b'%PDF-') or hashlib.sha256(body).hexdigest() != digest:
            return None
        from scrapi.geollaqta_scraper import pdf_pages
        from .map_report import document_metrics
        pages = pdf_pages(body)
        document_metrics(pages, lot_id)  # Includes sector, block and lot validation.
        document['pages'] = pages
        root = data_dir() / lot_id[:6] / lot_id / 'map-reports'
        receipt = root / (selected + '-' + digest + '.shared')
        index_digest = hashlib.sha256(json.dumps(index, sort_keys=True).encode()).hexdigest().encode()
        if (root / name).is_file() and (not receipt.is_file() or receipt.read_bytes() != index_digest):
            save(lot_id, document, documents, body)
        return documents
    except FAILURES + (RuntimeError,):
        return None


def save(lot_id, document, documents, body):
    """Persist a validated live report; a mirror outage must not fail its query."""
    try:
        prefix = _prefix(lot_id)
        reports = _documents(lot_id, documents)
        selected = next((d for d in reports if d['record_id'] == document['record_id']), None)
        if not selected or not body.lstrip().startswith(b'%PDF-'):
            return
        digest = hashlib.sha256(body).hexdigest()
        name = 'reporte-' + selected['record_id'] + '-' + digest + '.pdf'
        metadata = {'schema': 1, 'lot_id': lot_id, 'record_id': selected['record_id'],
                    'source_url': selected['source_url'], 'sha256': digest,
                    'captured_at': datetime.now(timezone.utc).isoformat()}
        index = {'schema': 1, 'lot_id': lot_id, 'reports': reports}
        objects = [(name, body, 'application/pdf'),
                   (selected['record_id'] + '.json', json.dumps(metadata).encode(), 'application/json'),
                   ('index.json', json.dumps(index).encode(), 'application/json')]
        root = data_dir() / lot_id[:6] / lot_id / 'map-reports'
        for filename, content, _ in objects:
            _atomic(root / filename, content)
        cloud = R2(timeout=2)
        for filename, content, content_type in objects:
            # One bounded attempt per object; publish the index only after both
            # original and metadata are acknowledged with length and SHA256.
            cloud._put_verified(prefix + filename, content, content_type)
        receipt = root / (selected['record_id'] + '-' + digest + '.shared')
        _atomic(receipt, hashlib.sha256(json.dumps(index, sort_keys=True).encode()).hexdigest().encode())
    except FAILURES:
        logger.warning('No se pudo compartir la copia del reporte catastral %s; la consulta verificada se conserva.', lot_id)
