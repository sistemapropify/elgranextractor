"""Canonical lot dossier published by the Catastro Maestro.

The ACM and the master map are readers of this contract. Normalized D1 data is
preferred. An independently archived R2 manifest remains visible while its lot
has not yet been normalized, without querying the original cadastral service.
"""
import hashlib
import json
import re
from pathlib import PurePosixPath
from urllib.parse import quote

from django.core.cache import cache

from .master_d1 import D1ReadModel
from .master_ingest import prepare
from .storage import R2, StorageError


SCHEMA = 'prometeo-catastro-master-dossier-v1'


def validate_lot(lot_id):
    if not re.fullmatch(r'\d{14}', str(lot_id or '')):
        raise ValueError('Código catastral no válido.')
    return str(lot_id)


def _surface(surface):
    if surface not in ('master', 'acm'):
        raise ValueError('Superficie de consulta no válida.')
    return surface


def _object_filename(key):
    return PurePosixPath(str(key or '')).name


def _archive_url(lot_id, filename, surface):
    safe = quote(filename, safe='')
    if surface == 'acm':
        return '/acm/catastro/lotes/' + lot_id + '/archivos/' + safe + '/'
    return '/catastro/api/maestro/lotes/' + lot_id + '/archivos/' + safe + '/'


def _media_url(item, lot_id, surface):
    if item.get('id'):
        prefix = '/acm/catastro/medios/' if surface == 'acm' else '/catastro/api/maestro/medios/'
        return prefix + quote(str(item['id']), safe='') + '/'
    filename = item.get('filename') or _object_filename(item.get('object_key'))
    return _archive_url(lot_id, filename, surface) if filename else None


def _normalized_media_urls(value, lot_id, surface):
    for item in value.get('media') or []:
        item['filename'] = item.get('filename') or _object_filename(item.get('object_key'))
        item['url'] = _media_url(item, lot_id, surface)
    for item in value.get('gallery') or []:
        item['url'] = _media_url(item, lot_id, surface)
    return value


def _from_d1(lot_id, record_id, surface):
    model = D1ReadModel()
    identity = model.lot_identity(lot_id)
    if not identity:
        return None
    data = model.entity(identity['entity_id'])
    attributes = dict(data.get('attributes') or {})
    units = []
    choices = []
    for unit in data.get('unit_attributes') or []:
        record = str(unit.get('source_feature_id') or '')
        if not record:
            continue
        choices.append(record)
        units.append({**unit, 'record_id': record})
    if record_id and record_id not in choices:
        raise ValueError('La ficha no pertenece al lote vinculado.')
    selected = record_id or (choices[0] if choices else '')
    media = []
    for item in data.get('media') or []:
        details = item.get('details') or {}
        media.append({
            **item,
            'filename': _object_filename(item.get('object_key')),
            'record_id': details.get('source_record_id'),
        })
    reports = []
    seen = set()
    for record in choices:
        if record in seen:
            continue
        seen.add(record)
        reports.append({'record_id': record, 'form_number': ''})
    for item in media:
        record = str(item.get('record_id') or '')
        if record and record not in seen:
            seen.add(record)
            reports.append({'record_id': record,
                            'form_number': (item.get('details') or {}).get('form_number', '')})
    gallery = [
        item for item in media
        if re.search(r'facade|photo|image|foto', str(item.get('kind') or ''), re.I)
    ]
    value = {
        'schema': SCHEMA,
        'lot_id': lot_id,
        'master_revision': data.get('master_revision'),
        'source_origin': 'GeoLlaqta · COFOPRI',
        'master_status': 'normalized_d1',
        'published_by': 'Catastro Maestro',
        'attributes': attributes,
        'units': units,
        'unit_attributes': units,
        'owners': data.get('owners') or [],
        'media': media,
        'gallery': gallery,
        'documents': media,
        'reports': reports,
        'selected_record_id': selected,
        'identity_links': data.get('identity_links') or [],
        'relationships': data.get('relationships') or [],
        'provenance': data.get('provenance') or {},
        'boundary_segments': data.get('boundary_segments') or [],
        'registral_acts': data.get('registral_acts') or [],
        'catalog': data.get('catalog') or {},
        'missing': [],
        'source_manifest': None,
        'master': {
            'entity_id': identity['entity_id'],
            'source_version_id': identity.get('version_id'),
            'source_id': identity.get('source_id'),
            'source_feature_id': lot_id,
            'selected_entity_id': next(
                (unit.get('id') for unit in units if unit.get('record_id') == selected),
                identity['entity_id']),
        },
    }
    return _normalized_media_urls(value, lot_id, surface)


def _archive_manifest(lot_id, cloud=None):
    cloud = cloud or R2(timeout=15)
    key = 'geollaqta/' + lot_id[:6] + '/' + lot_id + '/datos.json'
    body, _ = cloud.get_manifest(key)
    digest = hashlib.sha256(body).hexdigest()
    value = json.loads(body)
    if (not isinstance(value, dict) or value.get('lot_id') != lot_id or
            value.get('district_ubigeo') != lot_id[:6]):
        raise StorageError('El archivo del lote no corresponde a su código catastral.')
    return value, digest


def _from_archive(lot_id, record_id, surface, cloud=None):
    manifest, digest = _archive_manifest(lot_id, cloud)
    payload = prepare(manifest, source_verified=True)
    features = payload.get('features') or []
    lot = next((item for item in features if item.get('kind') == 'lote'), None)
    if not lot:
        raise StorageError('El archivo del lote no contiene una entidad de lote.')
    units = []
    choices = []
    for item in features:
        if item.get('kind') not in ('unidad', 'registro_documental'):
            continue
        record = str(item.get('id') or '')
        choices.append(record)
        units.append({
            'id': item.get('suggested_internal_id'),
            'record_id': record,
            'source_feature_id': record,
            'kind': item.get('kind'),
            **(item.get('fields') or {}),
        })
    if record_id and record_id not in choices:
        raise ValueError('La ficha no pertenece al lote archivado.')
    selected = record_id or (choices[0] if choices else '')
    artifacts = {
        str(item.get('filename')): item
        for item in manifest.get('artifacts') or []
        if item.get('filename')
    }
    media = []
    gallery = []
    for item in payload.get('media') or []:
        kind = str(item.get('kind') or '')
        filename = _object_filename(item.get('object_key'))
        if not filename or filename not in artifacts:
            continue
        row = {
            'id': None,
            'kind': kind,
            'object_key': item.get('object_key'),
            'filename': filename,
            'sha256': item.get('sha256'),
            'record_id': item.get('source_record_id'),
            'source_record_id': item.get('source_record_id'),
            'observed_at': manifest.get('retrieved_at'),
            'details': {'source_record_id': item.get('source_record_id')},
        }
        row['url'] = _media_url(row, lot_id, surface)
        media.append(row)
        if re.search(r'facade|photo|image|foto', kind, re.I):
            gallery.append(dict(row))
    reports = []
    seen = set()
    for item in manifest.get('reports') or []:
        record = str(item.get('record_id') or '')
        if not record or record in seen:
            continue
        seen.add(record)
        reports.append({
            'record_id': record,
            'form_number': item.get('form_number') or item.get('document_name') or '',
            'document_type': item.get('type') or '',
        })
    for record in choices:
        if record not in seen:
            seen.add(record)
            reports.append({'record_id': record, 'form_number': '', 'document_type': ''})
    owners = []
    for item in payload.get('people') or []:
        owners.append({
            'name': item.get('name'),
            'document_type': item.get('document_type'),
            'document_number': item.get('document_number'),
            'kind': 'titular',
            'share': item.get('share'),
            'condition': item.get('condition'),
            'source_record_id': item.get('source_record_id'),
            'details': item,
        })
    value = {
        'schema': SCHEMA,
        'lot_id': lot_id,
        'master_revision': None,
        'source_origin': 'GeoLlaqta · COFOPRI',
        'master_status': 'archived_pending_d1',
        'published_by': 'Catastro Maestro',
        'attributes': lot.get('fields') or {},
        'units': units,
        'unit_attributes': units,
        'owners': owners,
        'media': media,
        'gallery': gallery,
        'documents': media,
        'reports': reports,
        'selected_record_id': selected,
        'identity_links': [],
        'relationships': payload.get('relationships') or [],
        'provenance': lot.get('provenance') or {},
        'boundary_segments': payload.get('boundary_segments') or [],
        'registral_acts': payload.get('registral_acts') or [],
        'catalog': {},
        'missing': manifest.get('missing') or [],
        'source_manifest': {
            'object_key': 'geollaqta/' + lot_id[:6] + '/' + lot_id + '/datos.json',
            'sha256': digest,
            'retrieved_at': manifest.get('retrieved_at'),
        },
        'master': {
            'entity_id': None,
            'source_version_id': None,
            'source_id': 'archivo-geollaqta-' + lot_id[:6],
            'source_feature_id': lot_id,
            'selected_entity_id': None,
        },
    }
    return _normalized_media_urls(value, lot_id, surface)


def load(lot_id, record_id=None, surface='master', cloud=None):
    lot_id = validate_lot(lot_id)
    surface = _surface(surface)
    record_id = str(record_id or '').strip() or None
    d1_error = None
    try:
        value = _from_d1(lot_id, record_id, surface)
    except StorageError as error:
        d1_error = str(error)
        value = None
    # Normalized D1 data is never served from an application cache. Every
    # consumer sees the latest committed revision on its next request.
    if value is not None:
        return value
    key = 'catastro-master-archive-dossier-v1:' + surface + ':' + lot_id + ':' + (record_id or '-')
    saved = cache.get(key)
    if saved is not None:
        return saved
    if value is None:
        try:
            value = _from_archive(lot_id, record_id, surface, cloud)
        except (ValueError, StorageError, json.JSONDecodeError):
            if d1_error:
                raise StorageError(d1_error) from None
            raise
    if d1_error and value.get('master_status') == 'archived_pending_d1':
        value['d1_warning'] = d1_error
    cache.set(key, value, 300)
    return value


def archive_asset(lot_id, filename, cloud=None):
    lot_id = validate_lot(lot_id)
    if not filename or filename != PurePosixPath(filename).name:
        raise ValueError('Archivo catastral no válido.')
    manifest, _ = _archive_manifest(lot_id, cloud)
    artifact = next((item for item in manifest.get('artifacts') or []
                     if str(item.get('filename') or '') == filename), None)
    if not artifact:
        raise ValueError('El archivo no pertenece al lote.')
    key = 'geollaqta/' + lot_id[:6] + '/' + lot_id + '/' + filename
    body, _ = (cloud or R2(timeout=20)).get(key, max_bytes=64_000_000)
    expected = str(artifact.get('sha256') or '')
    if expected and hashlib.sha256(body).hexdigest() != expected:
        raise ValueError('El archivo no coincide con su huella registrada.')
    if body.startswith(b'%PDF-'):
        content_type = 'application/pdf'
    elif body.startswith(b'\xff\xd8\xff'):
        content_type = 'image/jpeg'
    elif body.startswith(b'\x89PNG\r\n\x1a\n'):
        content_type = 'image/png'
    elif body.startswith((b'<!doctype html', b'<html')):
        content_type = 'text/html; charset=utf-8'
    else:
        raise ValueError('Formato de archivo no disponible.')
    return body, content_type


def summary(value, record_id=None):
    """Adapter used by the ACM while all source data comes from the master."""
    record_id = str(record_id or value.get('selected_record_id') or '').strip()
    units = value.get('unit_attributes') or value.get('units') or []
    if record_id and record_id not in {
            str(item.get('record_id') or item.get('source_feature_id') or '')
            for item in units}:
        raise ValueError('La ficha no pertenece al lote vinculado.')
    selected = next((item for item in units
                     if str(item.get('record_id') or item.get('source_feature_id') or '') == record_id),
                    units[0] if units else {})
    attributes = value.get('attributes') or {}
    metric = lambda item: None if item in (None, '') else item
    media = value.get('media') or []
    facade = next((item for item in value.get('gallery') or [] if item.get('url')), None)
    if facade is None:
        facade = next((item for item in media if item.get('url') and
                       re.search(r'facade|photo|image|foto',
                                 str(item.get('kind') or ''), re.I)), None)
    pdf = next((item for item in media if item.get('url') and
                str(item.get('kind') or '').lower().endswith('pdf') and
                str(item.get('record_id') or item.get('source_record_id') or '') == record_id),
               None)
    if pdf is None:
        pdf = next((item for item in media if item.get('url') and
                    str(item.get('kind') or '').lower().endswith('pdf')), None)
    reports = value.get('reports') or []
    selected_record = record_id or (str(selected.get('record_id') or
                                       selected.get('source_feature_id') or '')
                                    if selected else '')
    boundaries = {
        'frente': metric(selected.get('front')),
        'derecha': metric(selected.get('right')),
        'izquierda': metric(selected.get('left')),
        'fondo': metric(selected.get('back')),
    }
    master = value.get('master') or {}
    return {
        'lot_id': value['lot_id'],
        'metrics': {
            'land_area': metric(selected.get('land_area')),
            'built_area': metric(selected.get('built_area')),
            'floors': metric(selected.get('floors')
                             if selected.get('floors') is not None
                             else attributes.get('floors')),
            'units': metric(selected.get('units')
                            if selected.get('units') is not None
                            else attributes.get('units')),
            'perimeter': metric(selected.get('perimeter')),
            'boundaries': boundaries,
        },
        'gis_metrics': {
            'land_area': metric(attributes.get('gis_land_area')),
            'built_area': metric(attributes.get('gis_built_area')),
            'floors': metric(attributes.get('floors')),
            'units': metric(attributes.get('units')),
        },
        'verified': bool(value.get('master_status') == 'normalized_d1' or
                         any(item not in (None, '') for item in boundaries.values())),
        'facade_url': facade.get('url') if facade else None,
        'reports': reports,
        'selected_record_id': selected_record,
        'report_pdf_url': pdf.get('url') if pdf else None,
        'document_status': 'available' if (media or reports) else 'unavailable',
        'source_label': ('Catastro Maestro · D1'
                         if value.get('master_status') == 'normalized_d1'
                         else 'Catastro Maestro · archivo pendiente de normalización D1'),
        'master': master,
    }
