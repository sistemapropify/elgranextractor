"""Post-migration integrity gate between D1 storage and map exposure."""
import re
from datetime import datetime, timezone


def _read_many(gateway, queries):
    if hasattr(gateway, 'read_many'):
        return gateway.read_many(queries)
    return [gateway.read(query['sql'], query['params']) for query in queries]


def audit_district(gateway, ubigeo, expected_lots, revision=None):
    """Validate the district after all R2 lots have been linked in D1.

    Missing identities, duplicate identities, missing active geometry and
    missing current attributes are blocking errors. Incomplete optional source
    fields are reported as warnings and do not pretend to be verified data.
    """
    ubigeo = str(ubigeo or '')
    if not re.fullmatch(r'[0-9]{6}', ubigeo):
        raise ValueError('UBIGEO no válido para la auditoría.')
    expected = {str(value) for value in expected_lots or [] if value}
    if not expected:
        raise ValueError('No hay lotes esperados para auditar.')
    source_id = 'geollaqta-' + ubigeo
    lot_join = '''
        FROM identities i
        JOIN versions v ON v.id=i.version_id
        WHERE v.source_id=? AND i.layer='lote'
    '''
    queries = [
        {
            'sql': '''SELECT i.source_feature_id,i.entity_id
                      ''' + lot_join + '''
                      ORDER BY i.source_feature_id''',
            'params': [source_id],
        },
        {
            'sql': '''SELECT DISTINCT i.source_feature_id
                      FROM identities i
                      JOIN versions v ON v.id=i.version_id
                      JOIN selections s ON s.entity_id=i.entity_id
                       AND s.field='$geometry'
                      WHERE v.source_id=? AND i.layer='lote'
                      ORDER BY i.source_feature_id''',
            'params': [source_id],
        },
        {
            'sql': '''SELECT count(*) AS entities,
                             sum(CASE WHEN ca.entity_id IS NULL THEN 1 ELSE 0 END)
                               AS missing_current_attributes,
                             sum(CASE WHEN ca.land_area IS NOT NULL THEN 1 ELSE 0 END)
                               AS with_land_area,
                             sum(CASE WHEN ca.built_area IS NOT NULL THEN 1 ELSE 0 END)
                               AS with_built_area,
                             sum(CASE WHEN ca.front IS NOT NULL THEN 1 ELSE 0 END)
                               AS with_front,
                             sum(CASE WHEN ca.floors IS NOT NULL THEN 1 ELSE 0 END)
                               AS with_floors
                      FROM identities i
                      JOIN versions v ON v.id=i.version_id
                      LEFT JOIN current_attributes ca ON ca.entity_id=i.entity_id
                      WHERE v.source_id=? AND i.layer='lote' ''',
            'params': [source_id],
        },
        {
            'sql': '''SELECT m.kind,count(*) AS count
                      FROM media m
                      JOIN identities i ON i.entity_id=m.entity_id
                      JOIN versions v ON v.id=i.version_id
                      WHERE v.source_id=?
                      GROUP BY m.kind ORDER BY m.kind''',
            'params': [source_id],
        },
    ]
    rows, geometry_rows, attribute_rows, media_rows = _read_many(gateway, queries)
    entity_by_lot = {}
    for row in rows:
        lot_id = str(row['source_feature_id'])
        entity_by_lot.setdefault(lot_id, set()).add(str(row['entity_id']))
    identified = set(entity_by_lot)
    geometry = {str(row['source_feature_id']) for row in geometry_rows}
    attributes = attribute_rows[0] if attribute_rows else {}
    missing_identities = sorted(expected - identified)
    unexpected_identities = sorted(identified - expected)
    duplicate_entities = sorted(
        lot_id for lot_id, entities in entity_by_lot.items() if len(entities) != 1)
    missing_geometry = sorted(expected - geometry)
    missing_current = int(attributes.get('missing_current_attributes') or 0)
    errors = []
    if missing_identities:
        errors.append(str(len(missing_identities)) +
                      ' lotes R2 no tienen identidad en D1.')
    if unexpected_identities:
        errors.append(str(len(unexpected_identities)) +
                      ' identidades D1 no existen en el inventario R2.')
    if duplicate_entities:
        errors.append(str(len(duplicate_entities)) +
                      ' lotes tienen más de una entidad asociada.')
    if missing_geometry:
        errors.append(str(len(missing_geometry)) +
                      ' lotes no tienen geometría activa.')
    if missing_current:
        errors.append(str(missing_current) +
                      ' entidades de lote no tienen current_attributes.')
    warnings = []
    for key, label in (
        ('with_land_area', 'área de terreno'),
        ('with_built_area', 'área construida'),
        ('with_front', 'frente'),
        ('with_floors', 'pisos'),
    ):
        missing = max(0, len(expected) - int(attributes.get(key) or 0))
        if missing:
            warnings.append(str(missing) + ' lotes no aportan ' + label + '.')
    media = {str(row['kind']): int(row['count']) for row in media_rows}
    if not media:
        warnings.append('No hay medios vinculados a los lotes.')
    status = 'failed' if errors else ('warnings' if warnings else 'passed')
    return {
        'schema': 'catastro-migration-audit-v1',
        'ubigeo': ubigeo,
        'status': status,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'revision': revision,
        'source_lots': len(expected),
        'identified_lots': len(identified),
        'linked_lots': len(expected & identified & geometry),
        'missing_identities': len(missing_identities),
        'unexpected_identities': len(unexpected_identities),
        'duplicate_entities': len(duplicate_entities),
        'missing_geometry': len(missing_geometry),
        'missing_current_attributes': missing_current,
        'attribute_coverage': {
            key: int(attributes.get(key) or 0)
            for key in ('with_land_area', 'with_built_area', 'with_front', 'with_floors')
        },
        'media': media,
        'errors': errors,
        'warnings': warnings,
    }
