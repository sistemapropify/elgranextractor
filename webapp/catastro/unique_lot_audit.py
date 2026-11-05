"""Read-only estimate of unique lots across the three COFOPRI lot sources."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from shapely.geometry import shape
from shapely.strtree import STRtree

from cuadrantizacion import geollaqta
from . import vector_snapshots
from .storage import R2


def _properties(row, config):
    return vector_snapshots._normalized_properties(
        row['source'], 'lotes',
        geollaqta._properties(row['attributes'], config['fields']))


def live_lots(ubigeo, source):
    config = vector_snapshots.SOURCE_PROFILES[source]['layers']['lotes']
    inventory = vector_snapshots._query_profile(
        source, 'lotes',
        where="ID_DIST='%s'" % ubigeo, returnIdsOnly='true')
    ids = sorted(set(inventory.get('objectIds') or []))
    features = []
    for start in range(0, len(ids), 500):
        batch = vector_snapshots._query_profile(
            source, 'lotes',
            objectIds=','.join(map(str, ids[start:start + 500])),
            outFields=config['fields'], returnGeometry='true', outSR=4326)
        for row in batch.get('features') or []:
            attributes = geollaqta._properties(
                row.get('attributes') or {}, config['fields'])
            if attributes.get('ID_DIST') != ubigeo:
                continue
            try:
                geometry = geollaqta._esri_geometry(
                    row.get('geometry') or {}, 'polygon')
            except (ValueError, TypeError, IndexError, KeyError):
                continue
            features.append({
                'source': source,
                'id': attributes.get('OBJECTID'),
                'properties': vector_snapshots._normalized_properties(
                    source, 'lotes', attributes),
                'geometry': geometry,
            })
    return features


def archived_pcdpi_lots(ubigeo, cloud):
    try:
        return [
            {'source': 'pcdpi', **feature}
            for feature in vector_snapshots.read_snapshot(
                ubigeo, 'lotes', cloud=cloud, source='pcdpi')['features']
        ]
    except ValueError:
        return []


def identity(feature, ubigeo):
    properties = feature.get('properties') or {}
    rpu = str(properties.get('ID_PREDIO_RPU') or '').strip()
    if rpu:
        return ubigeo + ':RPU:' + rpu
    lot = str(properties.get('ID_LOTE') or '').strip()
    if lot:
        return ubigeo + ':LOTE:' + lot
    return '%s:%s:%s' % (
        ubigeo, feature.get('source'), feature.get('id'))


def _formal_groups(features, ubigeo):
    groups = {}
    for feature in features:
        key = identity(feature, ubigeo)
        groups.setdefault(key, []).append(feature)
    return groups


def _overlap_match(pcdpi, formal):
    if not pcdpi or not formal:
        return set(), 0
    formal_shapes = []
    formal_keys = []
    formal_centroids = []
    parcel_index = defaultdict(list)
    for key, entries in formal.items():
        for feature in entries:
            try:
                geometry = shape(feature['geometry'])
            except (KeyError, TypeError, ValueError):
                continue
            if geometry.is_empty or not geometry.is_valid:
                continue
            formal_shapes.append(geometry)
            formal_keys.append(key)
            formal_centroids.append(geometry.centroid)
            properties = feature.get('properties') or {}
            block = str(properties.get('COD_MZNA') or properties.get('NRO_MZNA') or '').strip().lstrip('0').upper()
            lot = str(properties.get('COD_LOTE') or properties.get('NRO_LOTE') or '').strip().lstrip('0').upper()
            if block and lot:
                parcel_index[(block, lot)].append((key, geometry.centroid))
    if not formal_shapes:
        return set(), 0
    tree = STRtree(formal_centroids)
    matched = set()
    comparisons = 0
    for feature in pcdpi:
        try:
            source_shape = shape(feature['geometry'])
        except (KeyError, TypeError, ValueError):
            continue
        if source_shape.is_empty or not source_shape.is_valid:
            continue
        properties = feature.get('properties') or {}
        block = str(properties.get('COD_MZNA') or '').strip().lstrip('0').upper()
        lot = str(properties.get('COD_LOTE') or '').strip().lstrip('0').upper()
        center = source_shape.centroid
        candidates = tree.query(center.buffer(.00012))
        best = None
        for index in candidates:
            target = formal_shapes[int(index)]
            centroid_distance = center.distance(formal_centroids[int(index)])
            same_parcel = any(
                key == formal_keys[int(index)] and
                center.distance(other_center) <= .00018
                for key, other_center in parcel_index.get((block, lot), []))
            if centroid_distance > .00006 and not same_parcel:
                continue
            intersection = source_shape.intersection(target).area
            smaller = min(source_shape.area, target.area)
            if not smaller:
                continue
            coverage = intersection / smaller
            score = min(coverage, 1.0)
            if ((coverage >= .6) or same_parcel) and (
                    best is None or score > best[0]):
                best = (score, formal_keys[int(index)])
        comparisons += len(candidates)
        if best:
            matched.add(best[1])
    return matched, comparisons


def audit(output_dir):
    cloud = R2(timeout=30)
    catalog = geollaqta.CATALOG['districts']
    rows = []
    total_pcdpi = total_unique = 0
    for district in catalog:
        ubigeo = district['ubigeo']
        pcdpi = archived_pcdpi_lots(ubigeo, cloud)
        wgs84 = live_lots(ubigeo, 'wgs84')
        psad56 = live_lots(ubigeo, 'psad56')
        pcdpi_unique = {
            key for key in (identity(item, ubigeo) for item in pcdpi)
        }
        formal = _formal_groups(wgs84 + psad56, ubigeo)
        matched, comparisons = _overlap_match(pcdpi, formal)
        unique = len(pcdpi_unique) + len(set(formal) - matched)
        row = {
            'ubigeo': ubigeo,
            'district': district['name'],
            'pcdpi_records': len(pcdpi),
            'pcdpi_unique': len(pcdpi_unique),
            'wgs84_records': len(wgs84),
            'psad56_records': len(psad56),
            'formalization_unique': len(formal),
            'pcdpi_formalization_matches': len(matched),
            'estimated_unique': unique,
            'increase_vs_pcdpi': unique - len(pcdpi_unique),
            'increase_percent': (
                round(100 * (unique - len(pcdpi_unique)) / len(pcdpi_unique), 2)
                if pcdpi_unique else None),
            'spatial_candidate_comparisons': comparisons,
        }
        rows.append(row)
        total_pcdpi += len(pcdpi_unique)
        total_unique += unique
        print(json.dumps(row, ensure_ascii=False), flush=True)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / 'estimacion_lotes_unicos_cofopri.csv'
    with csv_path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        'method': 'RPU-ID deduplication plus >=80% overlap of smaller parcel',
        'pcdpi_unique': total_pcdpi,
        'estimated_unique': total_unique,
        'increase': total_unique - total_pcdpi,
        'increase_percent': (
            round(100 * (total_unique - total_pcdpi) / total_pcdpi, 2)
            if total_pcdpi else None),
        'districts': rows,
    }
    (output_dir / 'estimacion_lotes_unicos_cofopri.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding='utf-8')
    return summary
