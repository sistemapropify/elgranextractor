"""Canonical lot dossier published by the Catastro Maestro.

The ACM and the master map are readers of this contract. Normalized D1 data is
preferred. An independently archived R2 manifest remains visible while its lot
has not yet been normalized, without querying the original cadastral service.
"""
import hashlib
import json
import math
import re
from pathlib import PurePosixPath
from urllib.parse import quote

from django.core.cache import cache

from .master_d1 import D1ReadModel
from .master_ingest import prepare
from .storage import R2, StorageError


SCHEMA = 'prometeo-catastro-master-dossier-v1'


def validate_lot(lot_id):
    if not re.fullmatch(r'[A-Za-z0-9-]{5,40}', str(lot_id or '')):
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


def _unique_rows(rows, key):
    result = []
    seen = set()
    for row in rows:
        value = key(row)
        if value in seen:
            continue
        seen.add(value)
        result.append(row)
    return result


def _merge_missing_attributes(attributes, data):
    for field, value in (data.get('attributes') or {}).items():
        if value in (None, '') or attributes.get(field) not in (None, ''):
            continue
        attributes[field] = value


def _merge_catalog(target, source):
    for key, values in (source or {}).items():
        if not isinstance(values, list):
            target.setdefault(key, values)
            continue
        target[key] = _unique_rows(
            [*(target.get(key) or []), *values],
            lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False),
        )


def _promote_shared_unit_values(attributes, units):
    """Promote a unit header only when every non-empty observation agrees."""
    for field in (
            'department', 'province', 'district', 'urbanization',
            'street_type', 'street_name', 'municipal_number',
            'cadastral_use', 'zoning', 'land_area', 'built_area',
            'front', 'back', 'left', 'right'):
        current = attributes.get(field)
        if isinstance(current, str) and ' | ' in current:
            parts = {part.strip() for part in current.split(' | ') if part.strip()}
            if len(parts) == 1:
                attributes[field] = parts.pop()
                current = attributes[field]
        if current not in (None, ''):
            continue
        values = set()
        for unit in units:
            value = unit.get(field)
            if value in (None, ''):
                continue
            value = str(value).strip()
            if ' | ' in value:
                alternatives = {
                    part.strip() for part in value.split(' | ') if part.strip()
                }
                if len(alternatives) == 1:
                    value = alternatives.pop()
            values.add(value)
        if len(values) == 1:
            attributes[field] = values.pop()


def _source_missing(attributes, owners, media, units):
    missing = []
    if attributes.get('urbanization') in (None, ''):
        missing.append('Urbanización no publicada por la fuente vectorial.')
    if (attributes.get('land_area') in (None, '')
            and attributes.get('gis_land_area') in (None, '')
            and attributes.get('geometric_land_area') in (None, '')):
        missing.append('Área de terreno no publicada; no se infiere un dato registral.')
    if attributes.get('built_area') in (None, '') and attributes.get('gis_built_area') in (None, ''):
        missing.append('Área construida no publicada por la fuente.')
    if not units:
        missing.append('Sin ficha documental o unidad registral vinculada.')
    if not owners:
        missing.append('Sin titulares publicados para este predio.')
    if not media:
        missing.append('Sin fotografía o documento catastral archivado.')
    return missing


def _measurement_total(value):
    """Sum official comma-separated side segments without treating them as one."""
    parts = [
        part.strip().replace(',', '.')
        for part in re.split(r'[;,|]', str(value or ''))
        if part.strip()
    ]
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        return None
    if not numbers or any(not math.isfinite(number) or number < 0
                          for number in numbers):
        return None
    return round(sum(numbers), 4), numbers


def _from_d1(lot_id, record_id, surface):
    model = D1ReadModel()
    identity = model.lot_identity(lot_id)
    if not identity:
        return None
    data = model.entity(identity['entity_id'])
    attributes = dict(data.get('attributes') or {})
    # PCDPI publishes cartographic measurements, not documentary areas.
    if str(identity.get('source_id') or '').startswith('cofopri-pcdpi-'):
        for documentary, source_value in (
                ('land_area', 'gis_land_area'),
                ('built_area', 'gis_built_area')):
            if (attributes.get(source_value) in (None, '')
                    and attributes.get(documentary) not in (None, '')):
                attributes[source_value] = attributes[documentary]
                attributes[documentary] = None

    related_entities = []
    related_loader = getattr(model, 'overlapping_lot_entities', None)
    primary_units = data.get('unit_attributes') or []
    primary_records = {
        str(unit.get('source_feature_id') or '')
        for unit in primary_units
        if unit.get('source_feature_id')
    }
    needs_related = (
        record_id and record_id not in primary_records
    ) or any(
        attributes.get(field) in (None, '')
        for field in (
            'urbanization', 'land_area', 'built_area',
            'street_name', 'municipal_number')
    ) or not data.get('owners') or not data.get('media')
    if related_loader and needs_related:
        try:
            matches = related_loader(identity['entity_id'], limit=4)
        except (StorageError, ValueError, TypeError):
            matches = []
        for match in matches:
            try:
                candidate = model.entity(match['entity_id'])
            except (StorageError, ValueError, TypeError):
                continue
            identity_link = next((
                link for link in (candidate.get('identity_links') or [])
                if link.get('layer') == 'lote'
            ), {})
            related_entities.append({
                **match,
                'source_feature_id': (
                    identity_link.get('source_feature_id')
                    or match.get('source_feature_id')),
            })
            _merge_missing_attributes(attributes, candidate)
            data['unit_attributes'] = _unique_rows(
                [*(data.get('unit_attributes') or []),
                 *(candidate.get('unit_attributes') or [])],
                lambda unit: str(
                    unit.get('id') or unit.get('record_id')
                    or unit.get('source_feature_id') or ''),
            )
            data['owners'] = _unique_rows(
                [*(data.get('owners') or []), *(candidate.get('owners') or [])],
                lambda owner: (
                    str(owner.get('id') or ''),
                    str(owner.get('name') or ''),
                    str(owner.get('document_type') or ''),
                    str(owner.get('document_number') or ''),
                    str(owner.get('source_record_id') or ''),
                ),
            )
            data['media'] = _unique_rows(
                [*(data.get('media') or []), *(candidate.get('media') or [])],
                lambda item: str(
                    item.get('id') or item.get('object_key')
                    or item.get('url') or ''),
            )
            for key in (
                    'relationships', 'boundary_segments', 'registral_acts',
                    'raw_fields', 'identity_links'):
                data[key] = _unique_rows(
                    [*(data.get(key) or []), *(candidate.get(key) or [])],
                    lambda row: json.dumps(
                        row, sort_keys=True, ensure_ascii=False, default=str),
                )
            for field, evidence in (candidate.get('provenance') or {}).items():
                data.setdefault('provenance', {}).setdefault(field, evidence)
            _merge_catalog(
                data.setdefault('catalog', {}),
                candidate.get('catalog') or {},
            )

    units = []
    choices = []
    for unit in data.get('unit_attributes') or []:
        record = str(unit.get('source_feature_id') or '')
        if not record:
            continue
        choices.append(record)
        units.append({**unit, 'record_id': record})
    _promote_shared_unit_values(attributes, units)
    geometry_metrics = data.get('geometry_metrics') or {}
    if (attributes.get('geometric_land_area') in (None, '')
            and geometry_metrics.get('area_m2') is not None):
        attributes['geometric_land_area'] = geometry_metrics['area_m2']
        data.setdefault('provenance', {})['geometric_land_area'] = {
            'source': 'Catastro Maestro · geometría D1',
            'status': 'calculated',
            'method': geometry_metrics.get('method'),
            'version_id': data.get('geometry_version_id'),
        }
    if record_id and record_id not in choices:
        raise ValueError('La ficha no pertenece al lote vinculado.')
    selected = record_id or (choices[0] if choices else '')
    boundary_details = {}
    for segment in data.get('boundary_segments') or []:
        side = str(segment.get('side') or '')
        if side in ('front', 'back', 'left', 'right'):
            evidence = json.loads(segment.get('evidence_json') or '{}')
            measurement = segment.get('length_m')
            segment_total = _measurement_total(evidence.get('raw_measure'))
            if measurement in (None, '') and segment_total:
                measurement = segment_total[0]
                evidence['segments_m'] = segment_total[1]
            if attributes.get(side) in (None, ''):
                attributes[side] = measurement
            boundary_details[side] = {
                **segment,
                'length_m': measurement,
                'evidence': evidence,
            }
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
        'raw_fields': data.get('raw_fields') or [],
        'boundary_details': boundary_details,
        'boundary_segments': data.get('boundary_segments') or [],
        'registral_acts': data.get('registral_acts') or [],
        'catalog': data.get('catalog') or {},
        'missing': _source_missing(
            attributes, data.get('owners') or [],
            data.get('media') or [], units),
        'source_manifest': None,
        'geometry': data.get('geometry'),
        'geometry_version_id': data.get('geometry_version_id'),
        'geometry_metrics': geometry_metrics,
        'related_entities': related_entities,
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


def _from_vector(lot_id, surface):
    """Publish a vector-only lot without inventing documents or owners."""
    from . import vector_snapshots
    feature = vector_snapshots.find_feature(
        lot_id[:6], 'lotes', 'ID_LOTE', lot_id)
    if not feature:
        return None
    properties = feature.get('properties') or {}
    attributes = {
        'ubigeo': lot_id[:6],
        'sector': properties.get('COD_SECT'),
        'block': properties.get('COD_MZNA'),
        'lot': properties.get('COD_LOTE'),
        'cadastral_year': properties.get('ANIO_CAT'),
        'zoning': properties.get('ZONIFICACION'),
        'gis_land_area': properties.get('AREA_TER'),
        'gis_built_area': properties.get('AREA_CON'),
        'floors': properties.get('NIVELES'),
        'units': properties.get('NRO_UNIDADES'),
    }
    attributes = {key: value for key, value in attributes.items()
                  if value not in (None, '')}
    return {
        'schema': SCHEMA,
        'lot_id': lot_id,
        'master_revision': None,
        'source_origin': 'GeoLlaqta · COFOPRI · vector archivado',
        'master_status': 'vector_snapshot',
        'published_by': 'Catastro Maestro',
        'attributes': attributes,
        'units': [],
        'unit_attributes': [],
        'owners': [],
        'media': [],
        'gallery': [],
        'documents': [],
        'reports': [],
        'selected_record_id': None,
        'identity_links': [],
        'relationships': [],
        'provenance': {
            key: {'source': 'vector archivado',
                  'source_field': source}
            for key, source in (
                ('sector', 'COD_SECT'), ('block', 'COD_MZNA'),
                ('lot', 'COD_LOTE'), ('cadastral_year', 'ANIO_CAT'),
                ('zoning', 'ZONIFICACION'),
                ('gis_land_area', 'AREA_TER'),
                ('gis_built_area', 'AREA_CON'),
                ('floors', 'NIVELES'), ('units', 'NRO_UNIDADES'))
            if key in attributes},
        'boundary_segments': [],
        'registral_acts': [],
        'catalog': {},
        'missing': ['Ficha, titulares, fotografías y documentos pendientes de archivo R2.'],
        'source_manifest': None,
        'master': {
            'entity_id': None,
            'source_version_id': None,
            'source_id': 'vectores-' + lot_id[:6],
            'source_feature_id': lot_id,
            'selected_entity_id': None,
        },
    }


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
        except StorageError as error:
            if error.http_status == 404:
                value = _from_vector(lot_id, surface)
                if value is not None:
                    value['d1_warning'] = d1_error or None
                    return value
            if d1_error:
                raise StorageError(d1_error) from None
            raise
        except (ValueError, json.JSONDecodeError):
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
        'frente': metric(
            selected.get('front')
            if selected.get('front') is not None
            else attributes.get('front')),
        'derecha': metric(
            selected.get('right')
            if selected.get('right') is not None
            else attributes.get('right')),
        'izquierda': metric(
            selected.get('left')
            if selected.get('left') is not None
            else attributes.get('left')),
        'fondo': metric(
            selected.get('back')
            if selected.get('back') is not None
            else attributes.get('back')),
    }
    boundary_details = value.get('boundary_details') or {}
    for label, side in (
            ('frente', 'front'), ('derecha', 'right'),
            ('izquierda', 'left'), ('fondo', 'back')):
        if boundaries[label] in (None, ''):
            boundaries[label] = metric(
                (boundary_details.get(side) or {}).get('length_m'))
    master = value.get('master') or {}
    master_metrics = {
        'land_area': metric(
            selected.get('land_area')
            if selected.get('land_area') is not None
            else attributes.get('land_area')),
        'built_area': metric(
            selected.get('built_area')
            if selected.get('built_area') is not None
            else attributes.get('built_area')),
        'floors': metric(
            selected.get('floors')
            if selected.get('floors') is not None
            else attributes.get('floors')),
        'units': metric(
            selected.get('units')
            if selected.get('units') is not None
            else attributes.get('units')),
        'perimeter': metric(
            selected.get('perimeter')
            if selected.get('perimeter') is not None
            else attributes.get('perimeter')),
        'boundaries': boundaries,
    }
    document_status = (
        'available' if (media or reports)
        else 'master_data_only'
        if any(
            item not in (None, '')
            for key, item in master_metrics.items()
            if key != 'boundaries'
        ) or any(item not in (None, '') for item in boundaries.values())
        else 'unavailable'
    )
    return {
        'lot_id': value['lot_id'],
        'metrics': master_metrics,
        'gis_metrics': {
            'land_area': metric(attributes.get('gis_land_area')),
            'built_area': metric(attributes.get('gis_built_area')),
            'floors': metric(attributes.get('floors')),
            'units': metric(attributes.get('units')),
        },
        'calculated_metrics': {
            'land_area': metric(
                (value.get('geometry_metrics') or {}).get('area_m2')),
            'perimeter': metric(
                (value.get('geometry_metrics') or {}).get('perimeter_m')),
        },
        'verified': bool(value.get('master_status') == 'normalized_d1' or
                         any(item not in (None, '') for item in boundaries.values())),
        'facade_url': facade.get('url') if facade else None,
        'reports': reports,
        'selected_record_id': selected_record,
        'report_pdf_url': pdf.get('url') if pdf else None,
        'document_status': document_status,
        'source_label': ('Catastro Maestro · D1'
                         if value.get('master_status') == 'normalized_d1'
                         else ('Catastro Maestro · vector archivado'
                               if value.get('master_status') == 'vector_snapshot'
                               else 'Catastro Maestro · archivo pendiente de normalización D1')),
        'master': master,
    }
