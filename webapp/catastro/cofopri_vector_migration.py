"""Stage deduplicated COFOPRI formalization vectors through MasterStore."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from shapely.geometry import shape
from shapely.strtree import STRtree

from . import master_contract
from . import master_store
from . import vector_snapshots
from .storage import R2


SOURCE_PREFIX = 'cofopri-formalizacion-'
IDENTIFIER_SCHEME = 'COFOPRI_RPU'


def _text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text[:2000] if text else None


def _number(value):
    if value in (None, ''):
        return None
    try:
        number = float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _integer(value):
    number = _number(value)
    return int(number) if number is not None else None


def _source_date(value):
    if isinstance(value, (int, float)):
        try:
            stamp = value / 1000 if value > 10**11 else value
            return datetime.fromtimestamp(
                stamp, tz=timezone.utc).date().isoformat()
        except (ValueError, OverflowError, OSError):
            return None
    text = str(value or '').strip()
    return text[:10] if text else None


def merged_formalization_lots(ubigeo, cloud=None):
    """Prefer PSAD56 and fill missing fields/geometry from WGS84 by RPU."""
    cloud = cloud or R2(timeout=30)
    grouped = {}
    for source in ('psad56', 'wgs84'):
        try:
            features = vector_snapshots.read_snapshot(
                ubigeo, 'lotes', cloud=cloud, source=source)['features']
        except ValueError:
            features = []
        for feature in features:
            properties = feature.get('properties') or {}
            rpu = str(properties.get('ID_PREDIO_RPU') or '').strip()
            key = rpu or '%s-%s' % (source, feature.get('id'))
            if key not in grouped:
                grouped[key] = {'id': key, 'source': source,
                                'properties': dict(properties),
                                'geometry': feature.get('geometry')}
                continue
            item = grouped[key]
            for name, value in properties.items():
                if item['properties'].get(name) in (None, '') and value not in (None, ''):
                    item['properties'][name] = value
            if not item.get('geometry') and feature.get('geometry'):
                item['geometry'] = feature['geometry']
    return [grouped[key] for key in sorted(grouped)]


def _feature(lot, ubigeo, district):
    properties = lot['properties']
    rpu = str(properties.get('ID_PREDIO_RPU') or '').strip()
    values = {
        'country_code': 'PE',
        'ubigeo': ubigeo,
        'department': 'Arequipa',
        'province': 'Arequipa',
        'district': district,
        'urbanization': _text(properties.get('NOMPJV')),
        'sector': _text(properties.get('COD_SECT')),
        'block': _text(properties.get('COD_MZNA') or properties.get('NRO_MZNA')),
        'lot': _text(properties.get('COD_LOTE') or properties.get('NRO_LOTE')),
        'land_area': _number(properties.get('AREA_TER')),
        'built_area': _number(properties.get('AREA_CON')),
        'floors': _integer(properties.get('NIVELES')),
        'units': _integer(properties.get('NRO_UNIDADES')),
        'cadastral_use': _text(
            properties.get('TIPO_USO') or properties.get('TIP_USO')),
    }
    values = {
        key: master_contract.validate_field(key, value)
        for key, value in values.items()
        if value not in (None, '')
    }
    provenance = {
        key: {
            'source': 'COFOPRI ' + lot['source'].upper(),
            'status': 'source_observation',
            **({'rpu': rpu} if rpu else {}),
        }
        for key in values
    }
    feature = {
        'id': lot['id'],
        'kind': 'lote',
        'fields': values,
        'provenance': provenance,
    }
    if lot.get('geometry'):
        feature['geometry'] = lot['geometry']
        provenance['$geometry'] = {
            'source': 'COFOPRI ' + lot['source'].upper(),
            'status': 'reprojected_by_arcgis_to_wgs84',
            'source_crs': (
                'EPSG:4248' if lot['source'] == 'psad56'
                else 'EPSG:4326'),
            **({'rpu': rpu} if rpu else {}),
        }
    return feature


def batch_payload(ubigeo, district, lots, index):
    source_id = SOURCE_PREFIX + ubigeo
    features = [_feature(lot, ubigeo, district) for lot in lots]
    digest = hashlib.sha256(json.dumps(
        [(item['id'], item.get('geometry')) for item in features],
        ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()
    version_id = source_id + ':' + digest[:24]
    identifiers = [
        {
            'target_ref': 'lote:' + feature['id'],
            'scheme': IDENTIFIER_SCHEME,
            'value': feature['id'],
            'status': 'candidate',
            'authority': 'COFOPRI',
        }
        for feature in features
        if feature['id'].startswith('P')
    ]
    return {
        'schema': master_contract.VERSION,
        'source': {
            'id': source_id,
            'name': 'COFOPRI · Formalización · ' + district,
            'ubigeo': ubigeo,
            'role': 'candidate',
        },
        'version': {
            'id': version_id,
            'label': 'Formalización RPU · %s · %s · %s' % (
                index, feature_id(features) or digest[:12], digest[:10]),
            'source_date': _source_date(
                next((lot['properties'].get('FECH_TRAN')
                      for lot in lots
                      if lot['properties'].get('FECH_TRAN')), None)),
            'crs': 'EPSG:4326',
            'georeferencing': {
                'status': 'verified',
                'method': 'ArcGIS reproyectó PSAD56 o WGS84 a EPSG:4326.',
                'evidence': {
                    'service': 'FORMALIZACION_PSAD56 / FORMALIZACION_WGS84',
                    'out_sr': 4326,
                },
            },
            'original': {
                'name': 'Vectores formalizados · ' + ubigeo,
                'canonical_sha256': digest,
                'archive_status': 'verified_vector_snapshot_r2',
            },
        },
        'features': features,
        'identifiers': identifiers,
        'warnings': [],
        'missing': [],
    }


def feature_id(features):
    return features[0]['id'] if features else None


def migrate_district(store, ubigeo, district, batch_size=100, limit=None,
                     actor='cofopri-formalizacion', progress=None):
    lots = merged_formalization_lots(ubigeo)
    source_id = SOURCE_PREFIX + ubigeo
    with store.lock:
        linked = {
            str(row[0]) for row in store.db.execute(
                '''SELECT i.source_feature_id FROM identities i
                   JOIN versions v ON v.id=i.version_id
                   WHERE v.source_id=? AND i.layer='lote' ''',
                (source_id,))
        }
    available = len(lots)
    lots = [lot for lot in lots if str(lot['id']) not in linked]
    if limit is not None:
        lots = lots[:int(limit)]
    batches = []
    for offset in range(0, len(lots), batch_size):
        chunk = lots[offset:offset + batch_size]
        payload = batch_payload(
            ubigeo, district, chunk, offset // batch_size + 1)
        staged = store.stage(payload, store.revision, actor)
        plan = {
            'revision': store.revision,
            'version_id': staged['version_id'],
            'mode': 'fill',
            'scope': {'ubigeo': ubigeo, 'kind': 'lote'},
            'fields': [],
            'reason': 'Incorporar formalización COFOPRI deduplicada por RPU.',
        }
        preview = store.preview(plan)
        applied = store.apply(plan, preview['token'], actor)
        item = {
            'batch': offset // batch_size + 1,
            'features': len(chunk),
            'version_id': staged['version_id'],
            'revision': applied.get('revision'),
            'processed': min(offset + len(chunk), len(lots)),
            'total': len(lots),
            'remaining': max(0, len(lots) - offset - len(chunk)),
        }
        batches.append(item)
        if progress:
            progress(item)
    return {
        'ubigeo': ubigeo,
        'district': district,
        'available_unique_lots': available,
        'already_linked': len(linked),
        'unique_formalization_lots': len(lots),
        'batches': batches,
    }


def _pcdpi_payload(ubigeo, district, matches, features, index):
    source_id = 'cofopri-pcdpi-' + ubigeo
    items = []
    identifiers = []
    for feature in features:
        properties = feature.get('properties') or {}
        lot_id = str(properties.get('ID_LOTE') or '').strip()
        if not lot_id:
            continue
        fields = {
            'country_code': 'PE',
            'ubigeo': ubigeo,
            'department': 'Arequipa',
            'province': 'Arequipa',
            'district': district,
            'sector': _text(properties.get('COD_SECT')),
            'block': _text(properties.get('COD_MZNA')),
            'lot': _text(properties.get('COD_LOTE')),
            'land_area': _number(properties.get('AREA_TER')),
            'built_area': _number(properties.get('AREA_CON')),
            'floors': _integer(properties.get('NIVELES')),
            'units': _integer(properties.get('NRO_UNIDADES')),
        }
        fields = {
            key: master_contract.validate_field(key, value)
            for key, value in fields.items() if value not in (None, '')
        }
        items.append({
            'id': lot_id,
            'kind': 'lote',
            'fields': fields,
            'geometry': feature.get('geometry'),
            'provenance': {
                key: {
                    'source': 'COFOPRI PCDPI',
                    'status': 'source_observation',
                }
                for key in [*fields, '$geometry']
            },
        })
        cuc = str(properties.get('CUC') or '').strip()
        if cuc:
            identifiers.append({
                'target_ref': 'lote:' + lot_id,
                'scheme': 'COFOPRI_CUC',
                'value': cuc,
                'status': 'candidate',
                'authority': 'COFOPRI',
            })
    digest = hashlib.sha256(json.dumps(
        [(item['id'], item.get('geometry')) for item in items],
        ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()
    version_id = source_id + ':' + digest[:24]
    payload = {
        'schema': master_contract.VERSION,
        'source': {
            'id': source_id,
            'name': 'COFOPRI · PCDPI · ' + district,
            'ubigeo': ubigeo,
            'role': 'candidate',
        },
        'version': {
            'id': version_id,
            'label': 'PCDPI · %s · %s' % (index, digest[:10]),
            'source_date': None,
            'crs': 'EPSG:4326',
            'georeferencing': {
                'status': 'verified',
                'method': 'COFOPRI PCDPI entregado por ArcGIS en EPSG:4326.',
                'evidence': {'service': 'Catastro_PCDPI/MapServer', 'out_sr': 4326},
            },
            'original': {
                'name': 'Vectores PCDPI · ' + ubigeo,
                'canonical_sha256': digest,
                'archive_status': 'verified_vector_snapshot_r2',
            },
        },
        'features': items,
        'identifiers': identifiers,
        'warnings': [],
        'missing': [],
    }
    return payload, matches


def augment_pcdpi_identities(store, ubigeo, district, cloud=None,
                             actor='cofopri-pcdpi-link'):
    """Link PCDPI codes to existing entities by block/lot and polygon overlap."""
    cloud = cloud or R2(timeout=30)
    try:
        pcdpi = vector_snapshots.read_snapshot(
            ubigeo, 'lotes', cloud=cloud, source='pcdpi')['features']
    except ValueError:
        return {'ubigeo': ubigeo, 'features': 0, 'linked': 0}
    current = store.collection(ubigeo, 'lote')['features']
    records = []
    for feature in current:
        try:
            geometry = shape(feature['geometry'])
        except (KeyError, TypeError, ValueError):
            continue
        if geometry.is_empty or not geometry.is_valid:
            continue
        properties = feature.get('properties') or {}
        records.append({
            'id': feature['id'],
            'block': str(properties.get('block') or '').strip().lstrip('0').upper(),
            'lot': str(properties.get('lot') or '').strip().lstrip('0').upper(),
            'geometry': geometry,
            'centroid': geometry.centroid,
        })
    if not records:
        return {'ubigeo': ubigeo, 'features': len(pcdpi), 'linked': 0}
    tree = STRtree([record['centroid'] for record in records])
    matches = {}
    for feature in pcdpi:
        properties = feature.get('properties') or {}
        lot_id = str(properties.get('ID_LOTE') or '').strip()
        if not lot_id:
            continue
        block = str(properties.get('COD_MZNA') or '').strip().lstrip('0').upper()
        lot = str(properties.get('COD_LOTE') or '').strip().lstrip('0').upper()
        try:
            source_geometry = shape(feature['geometry'])
        except (KeyError, TypeError, ValueError):
            continue
        center = source_geometry.centroid
        best = None
        for candidate_index in tree.query(center.buffer(.0008)):
            candidate = records[int(candidate_index)]
            same_parcel = candidate['block'] == block and candidate['lot'] == lot
            if same_parcel and center.distance(candidate['centroid']) <= .0008:
                best = (2.0, candidate)
                break
            intersection = source_geometry.intersection(
                candidate['geometry']).area
            smaller = min(source_geometry.area, candidate['geometry'].area)
            if smaller and intersection / smaller >= .7:
                score = intersection / smaller
                if best is None or score > best[0]:
                    best = (score, candidate)
        if best:
            matches[lot_id] = best[1]['id']
    if not matches:
        return {'ubigeo': ubigeo, 'features': len(pcdpi), 'linked': 0}
    payload, _ = _pcdpi_payload(
        ubigeo, district, matches, pcdpi, 1)
    staged = store.stage(payload, store.revision, actor)
    identity_map = {'lote:' + lot_id: entity_id
                    for lot_id, entity_id in matches.items()}
    plan = {
        'revision': store.revision,
        'version_id': staged['version_id'],
        'mode': 'fill',
        'scope': {'ubigeo': ubigeo, 'kind': 'lote'},
        'fields': [],
        'identity_map': identity_map,
        'reason': 'Vincular códigos PCDPI con las entidades formalizadas.',
    }
    preview = store.preview(plan)
    applied = store.apply(plan, preview['token'], actor)
    return {
        'ubigeo': ubigeo,
        'features': len(pcdpi),
        'linked': len(matches),
        'revision': applied.get('revision'),
        'version_id': staged['version_id'],
    }
