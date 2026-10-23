"""COFOPRI-to-master contract, built in memory without importing historical data."""
import hashlib
import json
import re
import uuid

from . import master_contract as contract


def prepare(manifest, source_verified=False):
    from .registry import normalize
    rows = normalize(manifest)
    lot = manifest['lot_id']
    manifest={key:value for key,value in manifest.items() if key!='master_candidate'}
    digest = hashlib.sha256(json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                      allow_nan=False, separators=(',', ':')).encode()).hexdigest()
    source_id = 'cofopri-' + lot
    result = {'schema': contract.VERSION, 'source': {'id': source_id, 'name': 'COFOPRI · ' + lot,
               'ubigeo': manifest['district_ubigeo'], 'role': 'candidate'},
              'version': {'id': source_id + '-' + digest[:24], 'label': digest,
                          'source_date': None, 'crs': 'EPSG:4326',
                          'georeferencing': ({'status': 'verified',
                              'method': 'Geometría entregada por COFOPRI en EPSG:4326.',
                              'evidence': {'service': 'Catastro_PCDPI/MapServer',
                                           'out_sr': 4326,
                                           'source_feature_id': lot}}
                            if source_verified else {'status': 'pending',
                              'method': 'Servicio COFOPRI solicitado con outSR=4326; requiere revisión de correspondencia.'}),
                          'original': {'name': 'datos.json', 'canonical_sha256': digest,
                                       'archive_status':'awaiting_verified_snapshot'}},
              'features': [], 'people': [], 'relationships': [], 'media': [],
              'raw_fields': [], 'warnings': [], 'missing': manifest.get('missing', []),
              'source_manifest_sha256': digest, 'retrieved_at': manifest.get('retrieved_at'),
              'raw_gis_attributes': (manifest.get('feature') or {}).get('attributes') or {}}
    known = {f['key'] for f in contract.fields()}
    matrix_fields = {'country_code': 'PE', 'ubigeo': manifest['district_ubigeo']}
    attrs = (manifest.get('feature') or {}).get('attributes') or {}
    for original, key in [('COD_SECT','sector'),('COD_MZNA','block'),('COD_LOTE','lot'),
                          ('MZNA_MUNI','address_block'),('LOTE_MUNI','address_lot')]:
        if attrs.get(original) not in (None, ''):
            matrix_fields[key] = str(attrs[original])
    matrix_evidence = {key: {'source': 'COFOPRI GIS', 'status': 'source_observation'} for key in matrix_fields}
    if isinstance(attrs.get('CUC'), str) and re.fullmatch(r'[A-Za-z0-9]{12}',attrs['CUC']):
        matrix_fields['cuc'] = attrs['CUC']
        matrix_evidence['cuc'] = {'source':'COFOPRI GIS','field':'CUC','status':'source_observation'}
    fid = lot
    rings = (manifest.get('feature') or {}).get('geometry', {}).get('rings', [])
    matrix = {'id': fid, 'kind': 'lote', 'fields': matrix_fields, 'provenance': matrix_evidence}
    if rings:
        from cuadrantizacion.geollaqta import _geometry
        # The adapter must preserve ESRI multipart/hole semantics. If unavailable,
        # retain the original instead of making a guessed Polygon.
        try:
            matrix['geometry'] = _geometry((manifest['feature'])['geometry'])
        except (TypeError, ValueError):
            result['warnings'].append('Geometría pendiente de normalización; original conservado.')
    result['features'].append(matrix)
    kinds = {}
    for row in rows:
        record_id = row.get('record_id')
        if not record_id:
            continue  # A missing document must not synthesize an independent unit.
        documents = [d for d in manifest.get('reports',[]) if str(d.get('record_id','')) == record_id]
        common = any('BIENES COMUNES' in str(d.get('document_name','')).upper() for d in documents)
        individual = any(d.get('type') in ('individual_record_pdf','cadastral_report_pdf') for d in documents)
        kind = 'unidad' if individual and not common else 'registro_documental'
        kinds[record_id] = kind
        values = {k: v for k, v in row.items() if k in known and v not in (None, '')}
        for key in list(values):
            if (row.get('provenance', {}).get(key) or {}).get('source') == 'GIS':
                matrix['fields'][key] = values.pop(key)
                matrix['provenance'][key] = row['provenance'][key]
        values.update(country_code='PE', ubigeo=manifest['district_ubigeo'])
        if 'use' in row and row['use'] not in (None, ''):
            values['cadastral_use'] = str(row['use'])
        for raw_cuc in (row.get('cuc_unit'),):
            if raw_cuc and re.fullmatch(r'[A-Za-z0-9]{12}', raw_cuc):
                values['cuc'] = raw_cuc
        clean = {}
        for key, value in values.items():
            try:
                clean[key] = contract.validate_field(key, value)
            except ValueError:
                result['warnings'].append('Valor conservado en originales; no normalizado: ' + key)
        item = {'id': record_id, 'kind': kind, 'fields': clean, 'provenance': row.get('provenance', {})}
        result['features'].append(item)
        result['relationships'].append({'kind': 'unidad_en_lote' if kind=='unidad' else 'documento_de_lote',
                                       'from': kind + ':' + record_id, 'to': 'lote:' + lot})
        for owner in row.get('owner_rows', []):
            # Preserve the documented row, including alignment status. Never
            # identify people by a name hash or infer current legal ownership.
            result['people'].append({'source_record_id': record_id, **owner})
        result['raw_fields'].append({'source_record_id': record_id, 'fields': row.get('fields', [])})
    for item in manifest.get('artifacts', []):
        name = item.get('filename', '')
        if name and '/' not in name and '\\' not in name:
            record = item.get('record_id')
            result['media'].append({'kind': item.get('type'), 'source_record_id': record,
                'target': (kinds.get(record,'registro_documental') + ':' + record) if record else ('lote:' + lot),
                'object_key': 'geollaqta/' + manifest['district_ubigeo'] + '/' + lot + '/' + name,
                'sha256': item.get('sha256'), 'source_url': item.get('source_url')})
    # Stable internal IDs are distinct from official CUC, registry and source IDs.
    for item in result['features']:
        item['suggested_internal_id'] = str(uuid.uuid5(uuid.NAMESPACE_URL,
            json.dumps(['catastro-maestro', 'PE', source_id, item['kind'], item['id']],
                       ensure_ascii=False, sort_keys=True, separators=(',', ':'))))
    return result
