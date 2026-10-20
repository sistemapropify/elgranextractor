"""Recover parcel linework from the Cayma EU-03 PDF, entirely in memory.

Only the requested, curated application layers are written with --output.
No image, PDF copy, collector state or intermediate geometry is persisted.
The PDF's ink paths have no CAD layer names or cadastral identifiers. Closed
faces are recovered by noding/polygonizing black linework; adjoining faces
are grouped as block candidates. Neither is an official cadastral inventory.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import fitz
from pyproj import Transformer, network
from shapely import normalize, to_wkb, set_precision
from shapely.geometry import LineString, Polygon, box, mapping
from shapely.ops import polygonize_full, transform, unary_union

SOURCE_ID = 'cayma-pud-2006-eu03'
SCALE = 1000 / 472.44
# Read from the printed kilometre grid (PDF points, top-left origin).
GRID = {'pdf_origin': [569.16, 328.55], 'utm_origin': [227000, 8197000],
        'metres_per_point': SCALE}
MAP_FRAME = (96.72, 328.55, 2458.86, 5525.333)
# Overview map and the legend/tables are page furniture, not survey geometry.
EXCLUSIONS = [(150, 380, 820, 1890), (1835, 4180, 2425, 5460)]


def segments(item):
    if item[0] == 'l':
        return [(item[1], item[2])]
    if item[0] == 'qu':
        q = item[1]
        points = [q.ul, q.ur, q.lr, q.ll, q.ul]
    elif item[0] == 're':
        r = item[1]
        points = [r.tl, r.tr, r.br, r.bl, r.tl]
    else:
        return []
    return list(zip(points, points[1:]))


def linework(drawings):
    mask = box(*MAP_FRAME)
    for exclusion in EXCLUSIONS:
        mask = mask.difference(box(*exclusion))
    lines, seen = [], set()
    for drawing in drawings:
        # Filled glyphs, zoning colours/hatching and raster tiles are omitted.
        if (drawing['type'] != 's' or drawing.get('color') != (0., 0., 0.)
                or drawing['width'] > .3):
            continue
        for item in drawing['items']:
            for a, b in segments(item):
                # Kilometre grid lines have no parcel semantics.
                if (max(abs(a.x-b.x), abs(a.y-b.y)) > 200
                        and (abs(a.x-b.x) < .02 or abs(a.y-b.y) < .02)):
                    continue
                pair = tuple(sorted((tuple(round(v, 2) for v in a),
                                     tuple(round(v, 2) for v in b))))
                if pair[0] == pair[1] or pair in seen:
                    continue
                seen.add(pair)
                line = LineString(pair)
                if mask.covers(line):
                    lines.append(line)
    return lines


def identity(geometry, kind):
    digest = hashlib.sha256(to_wkb(normalize(geometry))).hexdigest()[:20]
    return f'{SOURCE_ID}:{kind}:{digest}'


def recover(lines):
    faces, cuts, dangles, invalid = polygonize_full(unary_union(lines))
    parcels, rejected = [], Counter()
    for face in faces.geoms:
        area_m2 = face.area * SCALE**2
        # Suppress numerical slivers and very large undivided surroundings.
        if area_m2 < 20:
            rejected['small_or_sliver'] += 1
        elif area_m2 > 20000 or face.interiors:
            rejected['large_or_enclosing_face'] += 1
        elif face.area / face.length * SCALE < .35:
            rejected['narrow_sliver'] += 1
        else:
            parcels.append(face)
    # Union only adjoining recovered faces, never bridge a street with a buffer.
    merged = unary_union(parcels)
    blocks = list(merged.geoms) if merged.geom_type == 'MultiPolygon' else [merged]
    blocks.sort(key=lambda p: identity(p, 'manzana'))
    parcels.sort(key=lambda p: identity(p, 'lote'))
    return parcels, blocks, {
        'closed_faces': len(faces.geoms), 'rejected': dict(rejected),
        'cut_edges': len(cuts.geoms), 'dangling_edges': len(dangles.geoms),
        'invalid_rings': len(invalid.geoms),
        'minimum_face_area_m2': 20, 'maximum_face_area_m2': 20000,
        'complete_inventory': False,
    }


def page_to_utm(x, y, z=None):
    return 227000+(x-569.16)*SCALE, 8197000-(y-328.55)*SCALE


def rounded_geometry(geometry):
    # Rounding shared vertices independently can introduce self-intersections
    # around narrow block holes. GEOS snaps topology before serialization.
    value = mapping(set_precision(geometry, 1e-8, mode='valid_output'))
    def walk(coords):
        if isinstance(coords[0], (int, float)):
            return [round(coords[0], 8), round(coords[1], 8)]
        return [walk(c) for c in coords]
    return {'type': value['type'], 'coordinates': walk(value['coordinates'])}


def extract(path, output=None):
    original = Path(path).read_bytes()
    document = fitz.open(stream=original, filetype='pdf')
    if len(document) != 2 or tuple(document[1].rect) != (0., 0., 2551., 5811.):
        raise ValueError('This extraction profile only accepts the reviewed EU-03 PDF.')
    drawings = document[1].get_drawings()
    lines = linework(drawings)
    parcels, blocks, qa = recover(lines)
    network.set_network_enabled(False)
    project = Transformer.from_crs(24879, 4326, always_xy=True, allow_ballpark=False)
    from shapely.strtree import STRtree
    index = STRtree(blocks)
    block_ids = [identity(b, 'manzana') for b in blocks]
    def feature(geometry, kind):
        element_id = identity(geometry, kind)
        utm = transform(page_to_utm, geometry)
        geographic = transform(project.transform, utm)
        properties = {
            'ELEMENT_ID': element_id, 'SOURCE_ID': SOURCE_ID,
            'SOURCE_DATE': '2006-08', 'SOURCE_PAGE': 2, 'ID_DIST': '040103',
            'DISTRICT_NAME': 'Cayma', 'COD_SECT': None, 'COD_MZNA': None,
            'ANIO_CAT': None, 'REFERENCE_ONLY': True,
            'GEOMETRY_STATUS': 'recovered_unverified',
        }
        if kind == 'lote':
            owners = index.query(geometry.representative_point(), predicate='within')
            if len(owners) != 1:
                raise ValueError('A recovered parcel must belong to exactly one recovered block.')
            properties.update(ID_LOTE=None, COD_LOTE=None, BLOCK_REF=block_ids[owners[0]])
        else:
            properties.update(ID_MZNA=None)
        return {'type': 'Feature', 'id': element_id, 'properties': properties,
                'geometry': rounded_geometry(geographic)}
    layers = {'lotes': [feature(p, 'lote') for p in parcels],
              'manzanas': [feature(b, 'manzana') for b in blocks]}
    extent = transform(project.transform, transform(page_to_utm, unary_union(blocks))).bounds
    metadata = {
        'id': SOURCE_ID, 'name': 'Cayma · Plano municipal EU-03 (agosto de 2006)',
        'district': 'Cayma', 'ubigeo': '040103', 'source_date': '2006-08',
        'author': 'Municipalidad Distrital de Cayma · Equipo PUD/Cayma',
        'title': 'Plan Urbano Distrital de Cayma 2006–2015 · Plano de compatibilidades EU-03',
        'original_filename': Path(path).name, 'sha256': hashlib.sha256(original).hexdigest(),
        'source_url': 'https://www.scribd.com/document/723398697/cayma-plano-de-zonificacion-y-compatibilidad-vigente-compressed-1',
        'revision': 1, 'status': 'reference', 'active': True, 'reference_only': True,
        'crs': 'EPSG:4326', 'source_crs': 'EPSG:24879',
        'georeferencing': {
            'status': 'inferred_reference', 'datum_documented': False,
            'method': 'Printed kilometre grid; PSAD56 / UTM 19S inferred by landmark comparison.',
            'grid': GRID, 'accuracy_m': None,
            'controls': [
                {'name': 'Plaza de Cayma', 'lon': -71.54558, 'lat': -16.38148,
                 'pdf_point': [1176.21, 4802.87],
                 'reference': 'https://www.openstreetmap.org/way/138604601',
                 'check': 'PSAD56 places the point inside the plaza outline; WGS84/UTM is displaced.'},
            ],
        },
        'schema': 'prometeo-cadastral-geometry-v1',
        'bbox': [round(v, 8) for v in extent],
        'layers': {key: {'count': len(values), 'kind': 'polygon',
                         'origin': 'polygonized_pdf_linework' if key == 'lotes' else 'union_of_adjoining_recovered_faces'}
                   for key, values in layers.items()},
        'qa': {**qa, 'unique_input_segments': len(lines), 'drawing_paths': len(drawings)},
        'notes': [
            'Geometría de referencia de un plano de 2006; no acredita vigencia ni precisión catastral.',
            'Sin numeración original de manzana o lote. Los identificadores internos no son códigos catastrales.',
            'Manzanas reconstruidas al unir caras contiguas; contornos y agrupaciones pendientes de contraste.',
            'Sólo se recuperan caras cerradas; los segmentos abiertos no se convierten en lotes inventados.',
            'El datum se infiere por ubicación; la precisión no está certificada.',
        ],
    }
    if output:
        folder = Path(output)
        folder.mkdir(parents=True, exist_ok=True)
        (folder/'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        for key, values in layers.items():
            collection = {'type': 'FeatureCollection', 'name': key, 'source_id': SOURCE_ID,
                          'ubigeo': '040103', 'revision': 1, 'features': values}
            (folder/(key+'.geojson')).write_text(json.dumps(collection, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf8')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf')
    parser.add_argument('--output', help='Curated application source-data directory; no intermediate files.')
    args = parser.parse_args()
    print(json.dumps(extract(args.pdf, args.output), ensure_ascii=False, indent=2))
