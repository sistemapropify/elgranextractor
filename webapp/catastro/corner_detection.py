"""High-precision corner-lot suggestions from block and parcel geometry."""

import math
from collections import defaultdict

from shapely.geometry import shape
from shapely.ops import unary_union


DIRECTION_BUCKET_DEGREES = 30
MIN_DIRECTION_SEPARATION_DEGREES = 20


def _key(properties):
    return (
        str(properties.get('COD_SECT') or '').strip(),
        str(properties.get('COD_MZNA') or '').strip(),
    )


def _line_parts(geometry):
    if geometry.is_empty:
        return
    if geometry.geom_type in ('LineString', 'LinearRing'):
        yield geometry
    elif hasattr(geometry, 'geoms'):
        for child in geometry.geoms:
            yield from _line_parts(child)


def _direction_lengths(geometry):
    """Length by 30-degree axis bucket, measured in local metres."""
    lengths = defaultdict(float)
    for line in _line_parts(geometry):
        coordinates = list(line.coords)
        for start, end in zip(coordinates, coordinates[1:]):
            mid_latitude = math.radians((start[1] + end[1]) / 2)
            dx = (end[0] - start[0]) * 111_320 * math.cos(mid_latitude)
            dy = (end[1] - start[1]) * 110_540
            distance = math.hypot(dx, dy)
            if distance < 0.15:
                continue
            angle = math.degrees(math.atan2(dy, dx)) % 180
            bucket = int(angle // DIRECTION_BUCKET_DEGREES) * DIRECTION_BUCKET_DEGREES
            lengths[bucket] += distance
    return lengths


def _two_separate_frontages(lengths, min_frontage_m):
    directions = list(lengths)
    for index, first in enumerate(directions):
        for second in directions[index + 1:]:
            difference = abs(first - second)
            difference = min(difference, 180 - difference)
            if (difference >= MIN_DIRECTION_SEPARATION_DEGREES
                    and lengths[first] >= min_frontage_m
                    and lengths[second] >= min_frontage_m):
                return True
    return False


def detect_corner_lots(lots, blocks, min_frontage_m=3.0):
    """Return lot IDs with exterior frontage on at least two directions.

    The owning block comes from COD_SECT + COD_MZNA. Invalid or ungrouped
    geometries are skipped and reported separately instead of guessed.
    """

    blocks_by_key = defaultdict(list)
    lots_by_key = defaultdict(list)
    for feature in blocks:
        try:
            geometry = shape(feature.get('geometry') or {})
        except (TypeError, ValueError, KeyError):
            continue
        if geometry.is_empty or not geometry.is_valid:
            geometry = geometry.buffer(0)
        if not geometry.is_empty:
            blocks_by_key[_key(feature.get('properties') or {})].append(geometry)

    for feature in lots:
        lots_by_key[_key(feature.get('properties') or {})].append(feature)

    candidates = []
    skipped = 0
    for key, block_geometries in blocks_by_key.items():
        boundary = unary_union(block_geometries).boundary
        for feature in lots_by_key.get(key, []):
            properties = feature.get('properties') or {}
            lot_id = str(properties.get('ID_LOTE') or '').strip()
            if not lot_id:
                skipped += 1
                continue
            try:
                lot = shape(feature.get('geometry') or {})
            except (TypeError, ValueError, KeyError):
                skipped += 1
                continue
            if lot.is_empty or not lot.is_valid:
                lot = lot.buffer(0)
            if lot.is_empty:
                skipped += 1
                continue
            contact = lot.boundary.intersection(boundary)
            if _two_separate_frontages(
                _direction_lengths(contact),
                max(0.5, float(min_frontage_m)),
            ):
                candidates.append(lot_id)
    return sorted(set(candidates)), skipped
