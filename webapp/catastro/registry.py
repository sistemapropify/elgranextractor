"""Typed cadastral records and every extracted field, without inferring values."""
import hashlib
import json
import math
import re
import sqlite3
import time
import unicodedata
from urllib.parse import quote

VERSION = 1
TEXT_COLUMNS = {
    'lot_id': 'Código catastral del lote', 'record_id': 'Código de ficha / unidad',
    'district': 'Distrito', 'urbanization': 'Urbanización / habilitación urbana',
    'department': 'Departamento', 'province': 'Provincia', 'sector': 'Sector',
    'block': 'Manzana catastral', 'lot': 'Lote catastral',
    'address_block': 'Manzana de la dirección', 'address_lot': 'Lote de la dirección',
    'street_type': 'Tipo de vía', 'street_name': 'Nombre de vía', 'municipal_number': 'Número municipal',
    'cuc_lot': 'CUC del lote', 'cuc_unit': 'CUC de la unidad', 'use': 'Uso del predio',
    'owners': 'Titulares catastrales según documento', 'owner_document_type': 'Tipo de documento del titular',
    'owner_document_number': 'Documento del titular', 'ownership_share': 'Porcentaje de titularidad',
    'ownership_condition': 'Condición del titular', 'zoning': 'Zonificación (código de origen)',
    'water': 'Agua (valor de origen)', 'sewer': 'Desagüe (valor de origen)',
    'electricity': 'Electricidad (valor de origen)', 'telephone': 'Teléfono (valor de origen)',
    'cadastral_year': 'Año del catastro', 'report_date': 'Fecha del reporte',
    'front_boundary': 'Colindancia del frente', 'back_boundary': 'Colindancia del fondo',
    'left_boundary': 'Colindancia izquierda', 'right_boundary': 'Colindancia derecha',
    'document_status': 'Estado de los datos',
    'notary_name': '101 · Nombre de la notaría', 'notary_kardex': '102 · Kárdex',
    'deed_date': '103 · Fecha de escritura pública', 'registry_entry_type': '104 · Tipo de partida registral',
    'registry_entry_number': '105 · Número de partida registral', 'registry_folios': '106 · Fojas',
    'registry_seat': '107 · Asiento', 'property_registration_date': '108 · Fecha de inscripción del predio',
    'construction_declaration': '109 · Declaración de fábrica',
    'construction_registration_seat': '110 · Asiento de inscripción de fábrica',
    'construction_registration_date': '111 · Fecha de inscripción de fábrica',
}
NUMBER_COLUMNS = {
    'land_area': 'Área de terreno según documento (m²)', 'built_area': 'Área construida según documento (m²)',
    'front': 'Frente (m)', 'back': 'Fondo (m)', 'left': 'Izquierda (m)', 'right': 'Derecha (m)',
    'perimeter': 'Perímetro total consignado (m)', 'floors': 'Pisos (fuente GIS)', 'units': 'Unidades (fuente GIS)',
    'gis_land_area': 'Área de terreno GIS (m²)', 'gis_built_area': 'Área construida GIS (m²)',
}
COLUMNS = {**TEXT_COLUMNS, **NUMBER_COLUMNS}
ALIASES = {
    'DEPARTAMENTO': 'department', 'PROVINCIA': 'province', 'DISTRITO': 'district',
    'SECT': 'sector', 'MZA': 'block', 'URBANIZACION-HU': 'urbanization',
    'MANZANA': 'address_block', 'TIPO VIA': 'street_type', 'NOMBRE VIA': 'street_name',
    'NRO MUNICIPAL': 'municipal_number', 'CUC-LOTE': 'cuc_lot', 'CUC-UNIDAD CATASTRAL': 'cuc_unit',
    'AREA LOTE (M2)': 'land_area', 'AREA CONSTRUIDA (M2)': 'built_area', 'USO': 'use',
    'NOMBRES Y APELLIDOS O RAZON SOCIAL': 'owners', 'TIPO DOCUMENTO': 'owner_document_type',
    'NRO DOCUMENTO': 'owner_document_number', '(%)': 'ownership_share',
    'CONDICION DEL TITULAR': 'ownership_condition', 'FECHA': 'report_date',
    'PERIMETRO (M)': 'perimeter', 'PERIMETRO TOTAL (M)': 'perimeter',
}
GIS_ALIASES = {'COD_SECT': 'sector', 'COD_MZNA': 'block', 'COD_LOTE': 'lot',
               'MZNA_MUNI': 'address_block', 'LOTE_MUNI': 'address_lot',
               'ZONIFICACION': 'zoning', 'AGUA': 'water', 'DESAGUE': 'sewer',
               'LUZ': 'electricity', 'TELEFONO': 'telephone', 'ANIO_CAT': 'cadastral_year',
               'NIVELES': 'floors', 'NRO_UNIDADES': 'units',
               'AREA_TER': 'gis_land_area', 'AREA_CON': 'gis_built_area'}
REGISTRATION_FIELDS = {
    '101': ('notary_name', ('NOMBRE DE LA NOTARIA', 'NOMBRE NOTARIA')),
    '102': ('notary_kardex', ('KARDEX',)),
    '103': ('deed_date', ('FECHA DE ESCRITURA PUBLICA', 'FECHA ESCRITURA PUBLICA')),
    '104': ('registry_entry_type', ('TIPO DE PARTIDA REGISTRAL', 'TIPO PARTIDA REGISTRAL')),
    '105': ('registry_entry_number', ('NUMERO', 'NUMERO DE PARTIDA', 'NUMERO DE PARTIDA REGISTRAL')),
    '106': ('registry_folios', ('FOJAS',)), '107': ('registry_seat', ('ASIENTO',)),
    '108': ('property_registration_date', ('F DE INSC DEL PREDIO', 'FECHA DE INSCRIPCION DEL PREDIO')),
    '109': ('construction_declaration', ('DECL DE FABRICA', 'DECLARACION DE FABRICA')),
    '110': ('construction_registration_seat', ('AS INSC DE FABRICA', 'ASIENTO DE INSCRIPCION DE FABRICA')),
    '111': ('construction_registration_date', ('F DE INSC FABRIC', 'F DE INSC FABRICA', 'FECHA DE INSCRIPCION DE FABRICA')),
}


def folded(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '')).casefold()
                   if not unicodedata.combining(c))


def number(value):
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip()
    # No guessing at units, ranges, separators or mixed decimal conventions.
    if not re.fullmatch(r'\d+(?:[.,]\d+)?', raw):
        return None
    result = float(raw.replace(',', '.'))
    return result if math.isfinite(result) else None


def asset_url(lot_id, filename):
    return '/catastro/registros/archivo/' + quote(lot_id, safe='') + '/' + quote(filename, safe='') + '/'


def extract_owners(page, filename):
    """Align only the same printed row, never zip names and DNI by position."""
    labels = {'NOMBRES Y APELLIDOS O RAZON SOCIAL': 'name', 'TIPO DOCUMENTO': 'document_type',
              'NRO DOCUMENTO': 'document_number', '(%)': 'share', 'CONDICION DEL TITULAR': 'condition'}
    fields = [f for f in page.get('named_fields', []) if f.get('original_label') in labels]
    rows = {}
    for field in fields:
        role = labels[field['original_label']]
        spans = field.get('values', [])
        for value in spans:
            if value.get('row') is None:
                continue
            y = float(value['row'])
            row = next((old for old in rows if abs(old-y) <= 1), y)
            rows.setdefault(row, {}).setdefault(role, []).append(value)
    owners = []
    for y, values in sorted(rows.items()):
        if 'name' not in values:
            continue
        owner = {key: ' '.join(str(v['text']) for v in sorted(spans, key=lambda v: v.get('bbox', [0])[0]))
                 for key, spans in values.items()}
        owner.update(filename=filename, page=page.get('number'), row=y)
        owners.append(owner)
    if not owners:
        names = [f for f in fields if labels[f['original_label']] == 'name' and f.get('value')]
        if len(names) == 1:
            # A text-only extraction cannot establish a DNI/name relationship.
            owners.append({'name': str(names[0]['value']), 'filename': filename,
                           'page': page.get('number'), 'row': None, 'relationship_status': 'DNI no alineado'})
    return owners


def normalize(manifest):
    lot_id = str(manifest.get('lot_id', ''))
    district = str(manifest.get('district_ubigeo', ''))
    if not re.fullmatch(r'\d{6}', district) or not re.fullmatch(district + r'\d{8,12}', lot_id):
        raise ValueError('El índice no identifica correctamente el distrito y lote.')
    feature = manifest.get('feature') or {}
    attrs = feature.get('attributes') or {}
    geometry_lot = str(attrs.get('ID_LOTE') or '').strip()
    geometry_district = str(attrs.get('ID_DIST') or '').strip()
    if geometry_lot not in ('', lot_id) or geometry_district not in ('', district):
        raise ValueError('La geometría no corresponde al lote del índice.')
    artifacts = {a['filename']: a for a in manifest.get('artifacts', []) if a.get('filename')}
    photos = [asset_url(lot_id, name) for name, a in artifacts.items() if a.get('type') == 'facade_image']
    groups = {}
    for report in manifest.get('reports', []):
        rid = str(report.get('record_id', ''))
        if not re.fullmatch(district + r'\d{13}', rid):
            continue
        groups.setdefault(rid, []).append(report)
    if not groups:
        groups[''] = []
    records = []
    for record_id, documents in groups.items():
        row = {key: None for key in COLUMNS}
        row.update(id=lot_id + ':' + record_id, lot_id=lot_id, record_id=record_id,
                   ubigeo=district, fields=[], provenance={}, photo_urls=photos, pdf_urls=[],
                   owner_rows=[],
                   geometry=feature.get('geometry'), missing=manifest.get('missing', []),
                   source_retrieved_at=manifest.get('retrieved_at'), document_status='Sin documento extraído')
        for key, value in attrs.items():
            row['fields'].append({'section': 'GIS original', 'label': key, 'value': value, 'source': 'GIS'})
        for source, key in GIS_ALIASES.items():
            value = attrs.get(source)
            row[key] = number(value) if key in NUMBER_COLUMNS else str(value) if value is not None else None
            if row[key] is not None:
                row['provenance'][key] = {'source': 'GIS', 'field': source}
        mapped = False
        # Only named, mapped report headers feed the typed columns. Numbered
        # fields remain searchable individually, with their validation status.
        candidates = {}
        for document in documents:
            filename = str(document.get('filename', ''))
            artifact = artifacts.get(filename)
            if artifact and str(artifact.get('type', '')).endswith('pdf'):
                row['pdf_urls'].append({'url': asset_url(lot_id, filename),
                                        'name': document.get('document_name') or filename})
            for page in document.get('pages', []):
                row['owner_rows'].extend(extract_owners(page, filename))
                for kind in ('named_fields', 'numbered_fields', 'additional_fields'):
                    for field in page.get(kind, []):
                        entry = {k: field.get(k) for k in ('section', 'label', 'original_label', 'number', 'value', 'value_status')}
                        entry.update(source=kind, page=page.get('number'), filename=filename,
                                     document_type=document.get('type'), mapping_status=page.get('field_mapping_status'))
                        row['fields'].append(entry)
                        if field.get('value') in (None, ''):
                            continue
                        if kind == 'numbered_fields':
                            specification = REGISTRATION_FIELDS.get(str(field.get('number', '')).lstrip('0'))
                            raw_label = field.get('label') or field.get('original_label') or ''
                            clean_label = re.sub(r'[^A-Z0-9]+', ' ', folded(raw_label).upper()).strip()
                            if specification and clean_label in specification[1]:
                                candidates.setdefault(specification[0], []).append((str(field['value']).strip(), entry))
                            continue
                        if kind != 'named_fields':
                            continue
                        mapped = True
                        label = str(field.get('original_label', '')).strip().upper()
                        key = ALIASES.get(label)
                        if label == 'LOTE':
                            key = 'lot' if field.get('section') == 'Ubicación geográfica' else 'address_lot'
                        if label in ('FRENTE', 'FONDO', 'IZQUIERDA', 'DERECHA'):
                            side = {'FRENTE': 'front', 'FONDO': 'back', 'IZQUIERDA': 'left', 'DERECHA': 'right'}[label]
                            key = side if str(field.get('label', '')).startswith('Medida perimétrica') else side + '_boundary'
                        if key:
                            candidates.setdefault(key, []).append((str(field['value']).strip(), entry))
        conflicts = []
        for key, items in candidates.items():
            values = list(dict.fromkeys(value for value, _ in items))
            if len(values) > 1 and key != 'owners':
                row[key] = None
                conflicts.append(key)
                continue
            raw = ' | '.join(values) if key == 'owners' else values[0]
            row[key] = number(raw) if key in NUMBER_COLUMNS else raw
            row['provenance'][key] = {k: items[0][1].get(k) for k in ('filename', 'page', 'label')}
            if key in NUMBER_COLUMNS and row[key] is None:
                conflicts.append(key)
        row['document_status'] = ('Revisar discrepancias: ' + ', '.join(conflicts) if conflicts else
                                  'Campos de reporte extraídos' if mapped else 'Requiere revisión del diseño' if documents else
                                  'Sin documento extraído')
        records.append(row)
    return records


def connect(body=None):
    db = sqlite3.connect(':memory:')
    if body:
        db.deserialize(body)
    db.row_factory = sqlite3.Row
    db.create_function('folded', 1, folded, deterministic=True)
    db.execute('PRAGMA temp_store=MEMORY')
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS imports (lot_id TEXT PRIMARY KEY, digest TEXT NOT NULL, imported REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS properties (lot_id TEXT PRIMARY KEY, ubigeo TEXT NOT NULL, geometry TEXT);
        CREATE TABLE IF NOT EXISTS owners (id TEXT PRIMARY KEY, name TEXT NOT NULL,
            document_type TEXT, document_number TEXT, identity_status TEXT NOT NULL);
    ''')
    version = db.execute("SELECT value FROM meta WHERE key='version'").fetchone()
    if version and version[0] != str(VERSION):
        db.close()
        raise ValueError('Versión de índice catastral no compatible.')
    db.execute("INSERT OR IGNORE INTO meta VALUES ('version',?)", (str(VERSION),))
    definitions = ','.join('"' + key + '" ' + ('REAL' if key in NUMBER_COLUMNS else 'TEXT') +
                           (' REFERENCES properties(lot_id)' if key == 'lot_id' else '') for key in COLUMNS)
    db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, ubigeo TEXT NOT NULL, payload TEXT NOT NULL,' + definitions + ')')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS fields (record_key TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
            field_key TEXT NOT NULL, label TEXT NOT NULL, value TEXT, source TEXT);
        CREATE INDEX IF NOT EXISTS registry_lot ON records(lot_id);
        CREATE INDEX IF NOT EXISTS registry_district ON records(ubigeo);
        CREATE INDEX IF NOT EXISTS registry_urbanization ON records(urbanization);
        CREATE INDEX IF NOT EXISTS registry_block ON records(sector,block,lot);
        CREATE INDEX IF NOT EXISTS registry_fields ON fields(field_key,record_key);
        CREATE TABLE IF NOT EXISTS record_owners (record_key TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
            owner_id TEXT NOT NULL REFERENCES owners(id), share TEXT, condition TEXT,
            filename TEXT NOT NULL, page INTEGER, source_row REAL,
            UNIQUE(record_key,owner_id,filename,page,source_row));
        CREATE INDEX IF NOT EXISTS registry_owner_document ON owners(document_number);
    ''')
    db.commit()
    return db


def import_manifest(db, manifest, digest=None):
    rows = normalize(manifest)
    lot_id = manifest['lot_id']
    digest = digest or hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    prior = db.execute('SELECT digest FROM imports WHERE lot_id=?', (lot_id,)).fetchone()
    if prior and prior[0] == digest:
        return False
    db.execute('INSERT INTO properties VALUES (?,?,?) ON CONFLICT(lot_id) DO UPDATE SET ubigeo=excluded.ubigeo,geometry=excluded.geometry',
               (lot_id, manifest['district_ubigeo'], json.dumps(manifest.get('feature', {}).get('geometry'))))
    db.execute('DELETE FROM records WHERE lot_id=?', (lot_id,))
    names = ['id', 'ubigeo', 'payload', *COLUMNS]
    sql = 'INSERT INTO records (' + ','.join('"'+key+'"' for key in names) + ') VALUES (' + ','.join('?' for _ in names) + ')'
    for row in rows:
        db.execute(sql, [row['id'], row['ubigeo'], json.dumps(row, ensure_ascii=False), *(row[key] for key in COLUMNS)])
        for owner in row['owner_rows']:
            document_type, document_number = owner.get('document_type'), owner.get('document_number')
            # Without an explicitly aligned type and number, keep a source-local
            # identity. Identical names alone never merge people.
            reliable = bool(document_type and document_number)
            identity = [document_type, document_number] if reliable else [
                row['id'], owner['filename'], owner['page'], owner.get('row'), owner['name']]
            owner_id = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
            db.execute('INSERT OR IGNORE INTO owners VALUES (?,?,?,?,?)',
                       (owner_id, owner['name'], document_type, document_number,
                        'Documento y nombre extraídos' if reliable else 'Requiere cotejo de identidad'))
            previous_name = db.execute('SELECT name FROM owners WHERE id=?', (owner_id,)).fetchone()[0]
            if folded(previous_name) != folded(owner['name']):
                db.execute('UPDATE owners SET identity_status=? WHERE id=?',
                           ('Nombres discrepantes para el mismo documento; requiere cotejo', owner_id))
            db.execute('INSERT OR IGNORE INTO record_owners VALUES (?,?,?,?,?,?,?)',
                       (row['id'], owner_id, owner.get('share'), owner.get('condition'),
                        owner['filename'], owner['page'], owner.get('row')))
        for field in row['fields']:
            # Section + source distinguish identical labels with different meanings.
            key = json.dumps([field.get('source'), field.get('section'), field.get('label'), field.get('number')], ensure_ascii=False)
            label = ' · '.join(str(field[k]) for k in ('source', 'section', 'label') if field.get(k))
            value = field.get('value')
            db.execute('INSERT INTO fields VALUES (?,?,?,?,?)',
                       (row['id'], key, label, None if value is None else str(value), field.get('source')))
    db.execute('INSERT OR REPLACE INTO imports VALUES (?,?,?)', (lot_id, digest, time.time()))
    return True


def where(params):
    conditions, values = [], []
    for key in ('district', 'urbanization', 'owners', 'street_name', 'use'):
        if params.get(key):
            conditions.append('instr(folded(r."'+key+'"),folded(?))>0')
            values.append(str(params[key])[:300])
    for key in ('lot_id', 'record_id', 'sector', 'block', 'lot', 'registry_entry_number'):
        if params.get(key):
            conditions.append('r."'+key+'"=?')
            values.append(str(params[key])[:30])
    if params.get('owner_document_number'):
        conditions.append('EXISTS (SELECT 1 FROM record_owners ro JOIN owners o ON o.id=ro.owner_id '
                          'WHERE ro.record_key=r.id AND o.document_number=?)')
        values.append(str(params['owner_document_number'])[:100])
    for key in NUMBER_COLUMNS:
        for suffix, op in (('_min', '>='), ('_max', '<=')):
            raw = params.get(key+suffix)
            if raw not in (None, ''):
                value = number(raw)
                if value is None:
                    raise ValueError('Rango numérico no válido: '+COLUMNS[key])
                conditions.append('r."'+key+'"'+op+'?')
                values.append(value)
        low, high = params.get(key+'_min'), params.get(key+'_max')
        if low not in (None, '') and high not in (None, '') and number(low) > number(high):
            raise ValueError('El mínimo no puede superar al máximo.')
    if params.get('field_key'):
        conditions.append('EXISTS (SELECT 1 FROM fields f WHERE f.record_key=r.id AND f.field_key=? AND instr(folded(f.value),folded(?))>0)')
        values.extend([str(params['field_key'])[:1000], str(params.get('field_value', ''))[:300]])
    if params.get('q'):
        conditions.append('EXISTS (SELECT 1 FROM fields f WHERE f.record_key=r.id AND instr(folded(f.value),folded(?))>0)')
        values.append(str(params['q'])[:300])
    return (' WHERE ' + ' AND '.join(conditions) if conditions else ''), values


def query(db, params):
    clause, values = where(params)
    try:
        page = max(1, int(params.get('page', 1)))
        size = max(1, min(200, int(params.get('page_size', 50))))
    except (ValueError, TypeError):
        raise ValueError('Paginación no válida.') from None
    sort = str(params.get('sort', 'lot_id'))
    if sort not in COLUMNS:
        raise ValueError('Columna de ordenación no válida.')
    direction = 'DESC' if params.get('direction') == 'desc' else 'ASC'
    summary = dict(db.execute('SELECT COUNT(*) AS records, COUNT(DISTINCT lot_id) AS lots, '
                             'SUM(land_area IS NULL) AS missing_land, SUM(built_area IS NULL) AS missing_built '
                             'FROM records r'+clause, values).fetchone())
    rows = db.execute('SELECT payload FROM records r'+clause+' ORDER BY r."'+sort+'" '+direction+',r.id LIMIT ? OFFSET ?',
                      [*values, size, (page-1)*size]).fetchall()
    group = params.get('group', 'urbanization')
    if group not in ('district', 'urbanization', 'block'):
        raise ValueError('Agrupación no válida.')
    # Include district and sector when grouping blocks: codes repeat by sector.
    grouping = 'district,sector,block' if group == 'block' else 'district,urbanization' if group == 'urbanization' else 'district'
    groups = [dict(r) for r in db.execute('SELECT '+grouping+',COUNT(*) AS records,COUNT(DISTINCT lot_id) AS lots '
                                         'FROM records r'+clause+' GROUP BY '+grouping+' ORDER BY lots DESC LIMIT 200', values)]
    fields = [dict(row) for row in db.execute('SELECT field_key,label,COUNT(DISTINCT record_key) AS records FROM fields '
                                             'GROUP BY field_key,label ORDER BY label LIMIT 3000')]
    return {'rows': [json.loads(row[0]) for row in rows], 'summary': summary, 'groups': groups,
            'fields': fields, 'columns': COLUMNS, 'page': page, 'page_size': size,
            'indexed_lots': db.execute('SELECT COUNT(*) FROM imports').fetchone()[0]}
