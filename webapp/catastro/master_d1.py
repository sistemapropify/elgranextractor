"""Durable D1 composition through a private Worker; all working state stays RAM.

D1 remains authoritative. Optimistic revision guards and idempotent commits
protect independent app processes. No local database or download cache is used.
"""
import json
import os
from pathlib import Path
import time
import uuid
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError

from .master_store import MasterStore, Conflict, encoded
from .storage import NoRedirect, StorageError

TABLES = {'meta':('key',),'projects':('id',),'sources':('id',),'versions':('id',),
          'entities':('id',),'boundary_segments':('id',),'contributions':('id',),'identities':('version_id','layer','source_feature_id'),
          'selections':('entity_id','field'),'people':('id',),'relationships':('id',),'media':('id',),
          'registral_acts':('id',),'zones':('id',),'attribute_definitions':('id',),
          'administrative_areas':('id',),'addresses':('id',),
          'property_observations':('id',),'external_identifiers':('id',),'listings':('id',),
          'listing_observations':('id',),'transactions':('id',),'organizations':('id',),
          'activities':('id',),'visits':('id',),'developments':('id',),
          'development_lots':('id',),'development_stages':('id',),
          'environment_features':('id',),'coverage_records':('id',),
          'catalog_review_status':('target_table','target_id'),
          'catalog_review_events':('id',),
          'plan_workspace':('document_key',),'plan_notes':('id',),
          'current_attributes':('entity_id',),'journal':('revision',)}
MAX_SCOPE_ROWS = 800_000
MAX_SCOPE_BYTES = 384 * 1024 * 1024
# Pagination order must follow a D1 index. These tuples are only cursors for
# loading the same scoped rows; primary keys in TABLES still identify rows.
PAGE_KEYS = {
    'contributions': ('version_id', 'id'),
}


def _page_query(sql, keys, cursor):
    """Return a deterministic keyset page query without OFFSET scans."""
    if not cursor:
        return sql, []
    terms = []
    params = []
    for index, key in enumerate(keys):
        equal = [candidate + '=?' for candidate in keys[:index]]
        params.extend(cursor[:index])
        if equal:
            terms.append('(' + ' AND '.join(equal + [key + '>?']) + ')')
        else:
            terms.append(key + '>?')
        params.append(cursor[index])
    base, order = sql.rsplit(' ORDER BY ', 1)
    return base + ' AND (' + ' OR '.join(terms) + ') ORDER BY ' + order, params


def configuration():
    # App Service receives these as protected application settings. Local
    # previews keep using the private, out-of-repository secrets file.
    url=os.environ.get('CATASTRO_MASTER_GATEWAY_URL','')
    token=os.environ.get('CATASTRO_MASTER_GATEWAY_TOKEN','')
    if not url or not token:
        path=Path(os.environ.get('CATASTRO_MASTER_GATEWAY_FILE') or Path.home()/'.codex/secrets/prometeo-master-gateway.env')
        values=dict(line.strip().split('=',1) for line in path.read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith('#')) if path.is_file() else {}
        url=url or values.get('MASTER_GATEWAY_URL','')
        token=token or values.get('MASTER_TOKEN','')
    import re
    if not re.fullmatch(r'https://prometeo-catastro-maestro\.[a-z0-9-]+\.workers\.dev',url):
        raise StorageError('Configura el Worker privado del Catastro Maestro.')
    if len(token)<40:
        raise StorageError('Falta la credencial privada del Catastro Maestro.')
    return url,token


class Gateway:
    def __init__(self,url=None,token=None):
        self.url,self.token=(url,token) if url and token else configuration()
        self.opener=build_opener(NoRedirect())

    def call(self,payload):
        body=encoded(payload).encode()
        if len(body)>12*1024*1024:raise ValueError('Divide el cambio en ámbitos menores: supera 12 MB.')
        request=Request(self.url+'/v1/database',data=body,method='POST',headers={
            'Content-Type':'application/json','Authorization':'Bearer '+self.token,'User-Agent':'PrometeoCatastro/1.0'})
        for attempt in range(6):
            try:
                with self.opener.open(request,timeout=30) as response:
                    raw=response.read(24*1024*1024+1)
                if len(raw)>24*1024*1024:raise StorageError('Divide la consulta: la respuesta supera el límite seguro.')
                return json.loads(raw)
            except HTTPError as error:
                try:
                    detail=json.loads(error.read(4096) or b'{}').get('error','')
                except (ValueError, OSError, TypeError):
                    detail=''
                if error.code==409:raise Conflict('El maestro cambió. Actualiza y vuelve a comparar.') from None
                if error.code==413:raise StorageError('Divide la versión o el ámbito del cambio: excede los límites de la base actual.') from None
                overloaded = (
                    error.code == 400
                    and 'overloaded' in str(detail).lower()
                )
                if (error.code not in (429,500,502,503,504)
                        and not overloaded) or attempt == 5:
                    raise StorageError('El Catastro Maestro respondió HTTP '+str(error.code)+
                                       (': '+str(detail) if detail else '')+'.') from None
            except (URLError,OSError,TimeoutError):
                if attempt == 5:
                    raise StorageError('No se pudo confirmar el guardado en D1. Reintenta la misma operación.') from None
            time.sleep(min(20, 1.5 * (2 ** attempt)))
        raise StorageError('No se pudo contactar con D1.')

    def read(self,sql,params=()):
        return self.call({'action':'read','queries':[{'sql':sql,'params':list(params)}]})['results'][0]

    def read_many(self,queries):
        return self.call({'action':'read','queries':queries})['results']

    def revision(self):
        rows=self.read("SELECT value FROM meta WHERE key='revision'")
        if len(rows)!=1:raise StorageError('El esquema de D1 no está inicializado.')
        return int(rows[0]['value'])


class D1ReadModel:
    """Bounded read-only queries that never build the authoring working copy."""

    PAGE_SIZE = 10000

    def __init__(self, gateway=None):
        self.gateway = gateway or Gateway()

    def revision(self):
        return self.gateway.revision()

    def district_summaries(self, revision=None):
        query = """SELECT e.ubigeo,e.kind,COUNT(*) AS count
                   FROM entities e
                   JOIN selections s ON s.entity_id=e.id AND s.field='$geometry'
                   WHERE e.kind IN ('lote','manzana','via')
                   GROUP BY e.ubigeo,e.kind
                   ORDER BY e.ubigeo,e.kind"""
        bounds_query = """SELECT ubigeo,kind,MIN(lng) AS west,MIN(lat) AS south,
                                 MAX(lng) AS east,MAX(lat) AS north
                          FROM (
                            SELECT e.ubigeo,e.kind,
                                   json_extract(point.value,'$[0]') AS lng,
                                   json_extract(point.value,'$[1]') AS lat
                            FROM selections s
                            JOIN entities e ON e.id=s.entity_id
                            JOIN contributions c ON c.id=s.contribution_id
                            JOIN json_each(c.value_json,'$.coordinates[0]') point
                            WHERE s.field='$geometry'
                              AND json_extract(c.value_json,'$.type')='Polygon'
                            UNION ALL
                            SELECT e.ubigeo,e.kind,
                                   json_extract(point.value,'$[0]') AS lng,
                                   json_extract(point.value,'$[1]') AS lat
                            FROM selections s
                            JOIN entities e ON e.id=s.entity_id
                            JOIN contributions c ON c.id=s.contribution_id
                            JOIN json_each(c.value_json,'$.coordinates') polygon
                            JOIN json_each(polygon.value,'$[0]') point
                            WHERE s.field='$geometry'
                              AND json_extract(c.value_json,'$.type')='MultiPolygon'
                          )
                          GROUP BY ubigeo,kind
                          ORDER BY ubigeo,kind"""
        if revision is None:
            revision_rows, count_rows, bounds_rows = self.gateway.read_many([
                {'sql': "SELECT value FROM meta WHERE key='revision'", 'params': []},
                {'sql': query, 'params': []},
                {'sql': bounds_query, 'params': []},
            ])
            if len(revision_rows) != 1:
                raise StorageError('El esquema de D1 no está inicializado.')
            revision = int(revision_rows[0]['value'])
        else:
            count_rows, bounds_rows = self.gateway.read_many([
                {'sql': query, 'params': []},
                {'sql': bounds_query, 'params': []},
            ])
        summaries = {}
        for row in count_rows:
            item = summaries.setdefault(row['ubigeo'], {
                'ubigeo': row['ubigeo'], 'revision': revision,
                'lotes': 0, 'manzanas': 0, 'vias': 0,
            })
            if row['kind'] == 'lote':
                item['lotes'] = int(row['count'])
            elif row['kind'] == 'manzana':
                item['manzanas'] = int(row['count'])
            elif row['kind'] == 'via':
                item['vias'] = int(row['count'])
        for row in bounds_rows:
            item = summaries.get(row['ubigeo'])
            if not item:
                continue
            try:
                item['bbox'] = [float(row['west']), float(row['south']),
                                float(row['east']), float(row['north'])]
            except (TypeError, ValueError):
                continue
        return summaries

    def district_summary(self, ubigeo):
        return self.district_summaries().get(ubigeo)

    def district_catalog(self, revision=None):
        """Return current master inventory without scanning geometry bounds."""
        query = """SELECT e.ubigeo,e.kind,COUNT(*) AS count
                   FROM entities e
                   JOIN selections s ON s.entity_id=e.id AND s.field='$geometry'
                   WHERE e.kind IN ('lote','manzana','via')
                   GROUP BY e.ubigeo,e.kind
                   ORDER BY e.ubigeo,e.kind"""
        if revision is None:
            revision_rows, count_rows = self.gateway.read_many([
                {'sql': "SELECT value FROM meta WHERE key='revision'", 'params': []},
                {'sql': query, 'params': []},
            ])
            if len(revision_rows) != 1:
                raise StorageError('El esquema de D1 no está inicializado.')
            revision = int(revision_rows[0]['value'])
        else:
            count_rows = self.gateway.read(query)
        summaries = {}
        for row in count_rows:
            item = summaries.setdefault(row['ubigeo'], {
                'ubigeo': row['ubigeo'], 'revision': revision,
                'lotes': 0, 'manzanas': 0, 'vias': 0,
            })
            if row['kind'] == 'lote':
                item['lotes'] = int(row['count'])
            elif row['kind'] == 'manzana':
                item['manzanas'] = int(row['count'])
            elif row['kind'] == 'via':
                item['vias'] = int(row['count'])
        return summaries

    def lot_identity(self, source_feature_id):
        """Resolve a source lot code to the stable Catastro Maestro UUID."""
        try:
            value = str(source_feature_id or '').strip()
            valid = bool(value) and len(value) <= 40
        except TypeError:
            valid = False
        if not valid:
            raise ValueError('Código catastral no válido.')
        rows = self.gateway.read(
            '''SELECT i.entity_id,i.version_id,i.source_feature_id,
                      v.source_id,v.label AS version_label
               FROM identities i
               JOIN versions v ON v.id=i.version_id
               JOIN entities e ON e.id=i.entity_id
               WHERE i.layer='lote' AND i.source_feature_id=?
                 AND (v.source_id LIKE 'geollaqta-%'
                      OR v.source_id LIKE 'cofopri-%')
               ORDER BY v.created_at DESC LIMIT 1''',
            [value])
        return rows[0] if rows else None

    def entity(self, entity_id):
        """Read the complete normalized record with one bounded D1 batch."""
        try:
            uuid.UUID(entity_id)
        except (AttributeError, TypeError, ValueError):
            raise ValueError('Identificador maestro no válido.') from None
        queries = [
            ('revision', "SELECT value FROM meta WHERE key='revision'"),
            ('entity', 'SELECT * FROM entities WHERE id=?'),
            ('attributes', 'SELECT * FROM current_attributes WHERE entity_id=?'),
            ('owners', '''SELECT r.entity_id,p.id,p.name,p.document_type,p.document_number,
                r.kind,r.source_version,r.details_json
                FROM relationships r JOIN people p ON p.id=r.person_id
                WHERE r.entity_id=? OR r.entity_id IN (
                    SELECT entity_id FROM relationships
                    WHERE related_entity_id=? AND kind='unidad_en_lote')
                ORDER BY p.name'''),
            ('media', '''SELECT entity_id,id,kind,object_key,sha256,observed_at,source_version,
                details_json FROM media WHERE entity_id=? OR entity_id IN (
                    SELECT entity_id FROM relationships
                    WHERE related_entity_id=? AND kind='unidad_en_lote')
                ORDER BY kind,id'''),
            ('relationships', '''SELECT id,
                CASE WHEN entity_id=? THEN related_entity_id ELSE entity_id END
                    AS related_entity_id,kind,source_version
                FROM relationships
                WHERE (entity_id=? OR related_entity_id=?)
                  AND related_entity_id IS NOT NULL'''),
            ('provenance', '''SELECT s.field,c.version_id,c.evidence_json
                FROM selections s JOIN contributions c ON c.id=s.contribution_id
                WHERE s.entity_id=?'''),
            ('identity_links', '''SELECT i.entity_id,i.version_id,i.layer,i.source_feature_id,
                v.source_id,v.label AS version_label,s.name AS source_name,
                v.original_name,v.original_sha256
                FROM identities i JOIN versions v ON v.id=i.version_id
                LEFT JOIN sources s ON s.id=v.source_id
                WHERE i.entity_id=? OR i.entity_id IN (
                    SELECT entity_id FROM relationships
                    WHERE related_entity_id=? AND kind='unidad_en_lote')
                ORDER BY i.layer,v.created_at DESC'''),
            ('raw_fields', '''SELECT c.version_id,c.layer,c.source_feature_id,
                c.field,c.value_json,c.evidence_json
                FROM contributions c
                JOIN identities i ON i.version_id=c.version_id
                 AND i.layer=c.layer
                 AND i.source_feature_id=c.source_feature_id
                WHERE (i.entity_id=? OR i.entity_id IN (
                    SELECT entity_id FROM relationships
                    WHERE related_entity_id=? AND kind='unidad_en_lote'))
                  AND c.field LIKE '$raw:%'
                ORDER BY c.version_id,c.source_feature_id,c.field'''),
            ('boundary_segments', '''SELECT * FROM boundary_segments
                WHERE entity_id=? OR entity_id IN (
                    SELECT entity_id FROM relationships
                    WHERE related_entity_id=? AND kind='unidad_en_lote')'''),
            ('registral_acts', '''SELECT * FROM registral_acts
                WHERE entity_id=? OR entity_id IN (
                    SELECT entity_id FROM relationships
                    WHERE related_entity_id=? AND kind='unidad_en_lote')'''),
            ('addresses', '''SELECT address_type,full_address,street_type,street_name,
                municipal_number,interior,postal_code,precision,status,source_version
                FROM addresses WHERE entity_id=? ORDER BY address_type'''),
            ('observations', '''SELECT namespace,field_name,value_type,value_json,unit,
                method,status,observed_at,valid_from,valid_to,source_version
                FROM property_observations WHERE entity_id=? ORDER BY observed_at,id'''),
            ('identifiers', '''SELECT scheme,value,authority,scope,status,observed_at,
                source_version FROM external_identifiers WHERE entity_id=?
                ORDER BY scheme,value'''),
            ('listings', '''SELECT id,portal,external_id,url,operation,price,currency,
                area_value,area_unit,area_basis,status,first_seen,last_seen,source_version
                FROM listings WHERE entity_id=? ORDER BY last_seen DESC'''),
            ('listing_history', '''SELECT listing_id,observed_at,price,currency,operation,
                status,details_json,source_version FROM listing_observations
                WHERE listing_id IN (SELECT id FROM listings WHERE entity_id=?)
                ORDER BY observed_at DESC'''),
            ('transactions', '''SELECT transaction_type,amount,currency,transaction_date,
                recorded_date,source_version FROM transactions WHERE entity_id=?
                ORDER BY transaction_date DESC'''),
            ('activities', '''SELECT a.category,a.subcategory,a.activity_name,a.ciiu_code,
                a.ciiu_version,a.valid_from,a.valid_to,a.source_version,
                o.name AS organization_name,o.document_type AS organization_document_type,
                o.document_number AS organization_document_number
                FROM activities a LEFT JOIN organizations o ON o.id=a.organization_id
                WHERE a.entity_id=? ORDER BY a.valid_from DESC'''),
            ('visits', '''SELECT visited_at,observer,summary,details_json,source_version
                FROM visits WHERE entity_id=? ORDER BY visited_at DESC'''),
            ('development_links', '''SELECT d.id,d.name,d.status,d.expected_start,
                d.expected_end,l.role,l.source_version FROM development_lots l
                JOIN developments d ON d.id=l.development_id WHERE l.entity_id=?'''),
            ('unit_attributes', '''SELECT e.id,e.kind,
                (SELECT i.source_feature_id FROM identities i
                 WHERE i.entity_id=e.id AND i.layer='unidad'
                 ORDER BY i.version_id DESC LIMIT 1) AS source_feature_id,
                a.* FROM relationships r
                JOIN entities e ON e.id=r.entity_id
                LEFT JOIN current_attributes a ON a.entity_id=e.id
                WHERE r.related_entity_id=? AND r.kind='unidad_en_lote'
                  AND e.kind='unidad' ORDER BY e.id'''),
        ]
        parameter_counts = [
            0, 1, 1, 2, 2, 3, 1, 2, 2, 2, 2,
            1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        ]
        results = []
        for offset in range(0, len(queries), 10):
            results.extend(self.gateway.read_many([
                {
                    'sql': sql,
                    'params': [entity_id] * parameter_counts[index],
                }
                for index, (_, sql) in enumerate(
                    queries[offset:offset + 10], start=offset)
            ]))
        values = {name: rows for (name, _), rows in zip(queries, results)}
        if not values['entity']:
            raise ValueError('Inmueble no disponible.')

        def decoded(row, key, target):
            row = dict(row)
            if key in row:
                try:
                    row[target] = json.loads(row.pop(key) or '{}')
                except (TypeError, ValueError):
                    row[target] = {}
            return row

        owners = [decoded(row, 'details_json', 'details') for row in values['owners']]
        media = []
        for row in values['media']:
            item = decoded(row, 'details_json', 'details')
            item['url'] = '/catastro/api/maestro/medios/' + item['id'] + '/'
            media.append(item)
        provenance = {
            row['field']: {
                'version_id': row['version_id'],
                'evidence': decoded(row, 'evidence_json', 'evidence')['evidence'],
            }
            for row in values['provenance']
        }
        catalog = {
            'addresses': values['addresses'],
            'observations': [
                decoded(row, 'value_json', 'value') for row in values['observations']
            ],
            'identifiers': values['identifiers'],
            'listings': values['listings'],
            'listing_history': [
                decoded(row, 'details_json', 'details')
                for row in values['listing_history']
            ],
            'transactions': values['transactions'],
            'activities': values['activities'],
            'visits': [
                decoded(row, 'details_json', 'details') for row in values['visits']
            ],
            'development_links': values['development_links'],
        }
        return {
            'master_revision': (
                int(values['revision'][0]['value'])
                if values['revision'] else None),
            'entity': values['entity'][0],
            'attributes': values['attributes'][0] if values['attributes'] else {},
            'owners': owners,
            'media': media,
            'relationships': values['relationships'],
            'provenance': provenance,
            'identity_links': values['identity_links'],
            'raw_fields': [
                {
                    **{key: row[key] for key in (
                        'version_id', 'layer', 'source_feature_id', 'field')},
                    'value': decoded(
                        row, 'value_json', 'decoded')['decoded'],
                    'evidence': decoded(
                        row, 'evidence_json', 'decoded')['decoded'],
                }
                for row in values['raw_fields']
            ],
            'boundary_segments': values['boundary_segments'],
            'registral_acts': [
                decoded(row, 'details_json', 'details')
                for row in values['registral_acts']
            ],
            'unit_attributes': values['unit_attributes'],
            'catalog': catalog,
        }

    def canonical_source_info(self, ubigeo, kind):
        """Select one authoritative source family and its feature count."""
        priorities = [
            'cofopri-formalizacion-' + ubigeo,
            'cofopri-psad56-' + ubigeo,
            'cofopri-wgs84-' + ubigeo,
            'geollaqta-' + ubigeo,
            'cofopri-pcdpi-' + ubigeo,
        ]
        rows = self.gateway.read(
            '''SELECT v.source_id,COUNT(*) AS count
               FROM identities i
               JOIN versions v ON v.id=i.version_id
               JOIN entities e ON e.id=i.entity_id
               WHERE e.ubigeo=? AND i.layer=?
                 AND v.source_id IN (SELECT value FROM json_each(?))
               GROUP BY v.source_id''',
            [ubigeo, kind, encoded(priorities)],
        )
        available = {
            str(row['source_id']): int(row['count']) for row in rows
        }
        if available:
            source_id = max(
                available,
                key=lambda value: (
                    available[value],
                    -priorities.index(value),
                ),
            )
            return {
                'source_id': source_id,
                'count': available[source_id],
            }
        fallback = self.gateway.read(
            '''SELECT v.source_id,COUNT(*) AS count
               FROM identities i
               JOIN versions v ON v.id=i.version_id
               JOIN entities e ON e.id=i.entity_id
               WHERE e.ubigeo=? AND i.layer=?
               GROUP BY v.source_id
               ORDER BY count DESC,v.source_id
               LIMIT 1''',
            [ubigeo, kind],
        )
        if fallback:
            return {
                'source_id': str(fallback[0]['source_id']),
                'count': int(fallback[0]['count']),
            }
        return {'source_id': None, 'count': 0}

    def canonical_source(self, ubigeo, kind):
        return self.canonical_source_info(ubigeo, kind)['source_id']

    def collection_page(self, ubigeo, kind, revision=None, cursor='',
                        limit=2000):
        """Read one bounded keyset page of current entities from D1."""
        from .master_contract import validate_field
        validate_field('ubigeo', ubigeo)
        if kind not in ('lote', 'manzana', 'via'):
            raise ValueError('Capa no válida.')
        if type(limit) is not int or not 100 <= limit <= 10000:
            raise ValueError('Tamaño de página no válido.')
        rows = self.gateway.read(
            """SELECT e.id,e.kind,
                          (SELECT i.source_feature_id FROM identities i
                           JOIN versions iv ON iv.id=i.version_id
                           WHERE i.entity_id=e.id AND i.layer=e.kind
                           ORDER BY CASE WHEN iv.source_id LIKE
                             'cofopri-formalizacion-%' THEN 1 ELSE 0 END,
                             iv.created_at DESC LIMIT 1) AS source_feature_id,
                          (SELECT i.source_feature_id FROM identities i
                           JOIN versions iv ON iv.id=i.version_id
                           WHERE i.entity_id=e.id AND i.layer=e.kind
                             AND iv.source_id LIKE 'cofopri-formalizacion-%'
                           ORDER BY iv.created_at DESC LIMIT 1) AS formalization_rpu,
                          (SELECT iv.source_id FROM identities i
                           JOIN versions iv ON iv.id=i.version_id
                           WHERE i.entity_id=e.id AND i.layer=e.kind
                           ORDER BY CASE WHEN iv.source_id LIKE
                             'cofopri-formalizacion-%' THEN 1 ELSE 0 END,
                             iv.created_at DESC LIMIT 1) AS identity_source_id,
                          c.version_id AS geometry_version_id,
                          c.value_json AS geometry_json,
                          a.ubigeo,a.sector,a.block,a.lot,a.floors,a.units,
                          a.is_corner,a.is_through,a.faces_park,a.address,a.zoning
                   FROM entities e
                   JOIN selections s ON s.entity_id=e.id AND s.field='$geometry'
                   JOIN contributions c ON c.id=s.contribution_id
                   LEFT JOIN current_attributes a ON a.entity_id=e.id
                   WHERE e.ubigeo=? AND e.kind=? AND e.id>?
                   ORDER BY e.id
                   LIMIT """ + str(limit),
            [ubigeo, kind, str(cursor or '')],
        )
        features = []
        for row in rows:
            try:
                geometry = json.loads(row.get('geometry_json') or 'null')
            except (TypeError, ValueError):
                raise StorageError('D1 devolvió una geometría no válida.') from None
            if not isinstance(geometry, dict):
                continue
            properties = {
                key: value for key, value in row.items()
                if key not in ('id', 'kind', 'source_feature_id',
                               'geometry_version_id', 'geometry_json',
                               'entity_id', 'formalization_rpu',
                               'identity_source_id')
            }
            properties['source_feature_id'] = row.get('source_feature_id')
            properties['FORMALIZATION_RPU'] = row.get('formalization_rpu')
            properties['IDENTITY_SOURCE_ID'] = row.get('identity_source_id')
            features.append({
                'type': 'Feature', 'id': row['id'], 'geometry': geometry,
                'properties': properties,
                'provenance': {
                    '$geometry': {
                        'version_id': row.get('geometry_version_id'),
                    },
                },
            })
        return {
            'type': 'FeatureCollection',
            'features': features,
            'revision': revision if revision is not None else self.gateway.revision(),
            'crs': 'EPSG:4326',
            'next_cursor': rows[-1]['id'] if len(rows) == limit else None,
        }

    def collection(self, ubigeo, kind, revision=None):
        """Read all current entities using bounded keyset pages."""
        features = []
        cursor = ''
        revision = revision if revision is not None else self.gateway.revision()
        while True:
            page = self.collection_page(
                ubigeo, kind, revision=revision,
                cursor=cursor, limit=self.PAGE_SIZE)
            features.extend(page['features'])
            cursor = page.get('next_cursor')
            if not cursor:
                break
        return {
            'type': 'FeatureCollection',
            'features': features,
            'revision': revision,
            'crs': 'EPSG:4326',
        }

    def radius(self, ubigeo, lat, lng, metres, kind='lote'):
        """Read only current D1 lots/blocks whose polygons can touch a radius."""
        import math
        from .master_contract import validate_field
        validate_field('ubigeo', ubigeo)
        if kind not in ('lote', 'manzana', 'via'):
            raise ValueError('Capa no válida.')
        lat, lng, metres = float(lat), float(lng), float(metres)
        if (not all(math.isfinite(value) for value in (lat, lng, metres))
                or not -85 <= lat <= 85 or not -180 <= lng <= 180
                or not 100 <= metres <= 2000):
            raise ValueError('Ubicación o radio no válido.')
        sy = 6371008.8 * math.pi / 180
        sx = sy * math.cos(math.radians(lat))
        west, east = lng - metres / sx, lng + metres / sx
        south, north = lat - metres / sy, lat + metres / sy

        def inside(ring):
            hit = False
            for left, right in zip(ring, ring[1:]):
                if ((left[1] > lat) != (right[1] > lat)
                        and lng < (right[0] - left[0]) * (
                            lat - left[1]) / (right[1] - left[1]) + left[0]):
                    hit = not hit
            return hit

        def touches(geometry):
            if geometry.get('type') == 'LineString':
                for left, right in zip(
                        geometry.get('coordinates') or [],
                        (geometry.get('coordinates') or [])[1:]):
                    ax, ay = ((left[0] - lng) * sx,
                              (left[1] - lat) * sy)
                    bx, by = ((right[0] - lng) * sx,
                              (right[1] - lat) * sy)
                    dx, dy = bx - ax, by - ay
                    amount = max(0, min(
                        1, -(ax * dx + ay * dy) /
                        (dx * dx + dy * dy or 1)))
                    if ((ax + amount * dx) ** 2 +
                            (ay + amount * dy) ** 2
                            <= (metres + 0.1) ** 2):
                        return True
                return False
            polygons = ([geometry['coordinates']]
                        if geometry.get('type') == 'Polygon'
                        else geometry.get('coordinates') or [])
            for rings in polygons:
                if not rings:
                    continue
                if inside(rings[0]) and not any(
                        inside(ring) for ring in rings[1:]):
                    return True
                for ring in rings:
                    for left, right in zip(ring, ring[1:]):
                        ax, ay = ((left[0] - lng) * sx,
                                  (left[1] - lat) * sy)
                        bx, by = ((right[0] - lng) * sx,
                                  (right[1] - lat) * sy)
                        dx, dy = bx - ax, by - ay
                        amount = max(0, min(
                            1, -(ax * dx + ay * dy) /
                            (dx * dx + dy * dy or 1)))
                        if ((ax + amount * dx) ** 2 +
                                (ay + amount * dy) ** 2
                                <= (metres + 0.1) ** 2):
                            return True
            return False

        features = []
        cursor = ''
        page_size = 1000
        while True:
            rows = self.gateway.read(
                """SELECT e.id,e.kind,
                          (SELECT i.source_feature_id FROM identities i
                           JOIN versions iv ON iv.id=i.version_id
                           WHERE i.entity_id=e.id AND i.layer=e.kind
                           ORDER BY CASE WHEN iv.source_id LIKE
                             'cofopri-formalizacion-%' THEN 1 ELSE 0 END,
                             iv.created_at DESC LIMIT 1) AS source_feature_id,
                          (SELECT i.source_feature_id FROM identities i
                           JOIN versions iv ON iv.id=i.version_id
                           WHERE i.entity_id=e.id AND i.layer=e.kind
                             AND iv.source_id LIKE 'cofopri-formalizacion-%'
                           ORDER BY iv.created_at DESC LIMIT 1)
                             AS formalization_rpu,
                          (SELECT iv.source_id FROM identities i
                           JOIN versions iv ON iv.id=i.version_id
                           WHERE i.entity_id=e.id AND i.layer=e.kind
                           ORDER BY CASE WHEN iv.source_id LIKE
                             'cofopri-formalizacion-%' THEN 1 ELSE 0 END,
                             iv.created_at DESC LIMIT 1)
                             AS identity_source_id,
                          c.version_id AS geometry_version_id,
                          c.value_json AS geometry_json,
                          a.ubigeo,a.district,a.urbanization,a.sector,
                          a.block,a.lot,a.address,
                          a.street_type,a.street_name,a.zoning,
                          a.cadastral_use,a.land_area,a.built_area,
                          a.floors,a.units,a.is_corner,a.is_through,
                          a.faces_park
                   FROM entities e
                   JOIN selections s ON s.entity_id=e.id
                    AND s.field='$geometry'
                   JOIN contributions c ON c.id=s.contribution_id
                   LEFT JOIN current_attributes a ON a.entity_id=e.id
                   WHERE e.ubigeo=? AND e.kind=? AND e.id>?
                     AND (
                       (json_extract(c.value_json,'$.type')='Polygon'
                        AND EXISTS (
                          SELECT 1
                          FROM json_each(c.value_json,'$.coordinates[0]') point
                          WHERE json_extract(point.value,'$[0]')
                              BETWEEN ? AND ?
                            AND json_extract(point.value,'$[1]')
                              BETWEEN ? AND ?
                        ))
                       OR
                       (json_extract(c.value_json,'$.type')='LineString'
                        AND EXISTS (
                          SELECT 1
                          FROM json_each(c.value_json,'$.coordinates') point
                          WHERE json_extract(point.value,'$[0]')
                              BETWEEN ? AND ?
                            AND json_extract(point.value,'$[1]')
                              BETWEEN ? AND ?
                        ))
                       OR
                       (json_extract(c.value_json,'$.type')='MultiPolygon'
                        AND EXISTS (
                          SELECT 1
                          FROM json_each(c.value_json,'$.coordinates') polygon
                          JOIN json_each(polygon.value,'$[0]') point
                          WHERE json_extract(point.value,'$[0]')
                              BETWEEN ? AND ?
                            AND json_extract(point.value,'$[1]')
                              BETWEEN ? AND ?
                        ))
                     )
                   ORDER BY e.id LIMIT """ + str(page_size),
                [ubigeo, kind, cursor, west, east, south, north,
                 west, east, south, north,
                 west, east, south, north],
            )
            for row in rows:
                try:
                    geometry = json.loads(row.get('geometry_json') or 'null')
                except (TypeError, ValueError):
                    raise StorageError(
                        'D1 devolvió una geometría no válida.') from None
                if not isinstance(geometry, dict) or not touches(geometry):
                    continue
                properties = {
                    key: value for key, value in row.items()
                    if key not in ('id', 'kind', 'source_feature_id',
                                   'geometry_version_id', 'geometry_json',
                                   'entity_id', 'formalization_rpu',
                                   'identity_source_id')
                }
                properties['source_feature_id'] = row.get('source_feature_id')
                properties['FORMALIZATION_RPU'] = row.get('formalization_rpu')
                properties['IDENTITY_SOURCE_ID'] = row.get(
                    'identity_source_id')
                features.append({
                    'type': 'Feature',
                    'id': row['id'],
                    'geometry': geometry,
                    'properties': properties,
                    'provenance': {
                        '$geometry': {
                            'version_id': row.get('geometry_version_id'),
                        },
                    },
                })
            if len(rows) < page_size:
                break
            cursor = rows[-1]['id']
        return {
            'type': 'FeatureCollection',
            'features': features,
            'revision': self.gateway.revision(),
            'crs': 'EPSG:4326',
        }


class D1Store(MasterStore):
    """RAM working copy with a row-level, atomic and revision-guarded D1 commit.

The initial authoring cache is bounded to 384 MB/800k rows; exceeding it fails
explicitly and requires partitioned authoring. User query results stay bounded.
This is a correctness limit, never a silent subset of the master database.
"""
    def __init__(self,gateway=None,scope='040103'):
        super().__init__()
        self.gateway=gateway or Gateway()
        self.scope=scope
        self._select_scope(scope)
        self._dirty=True
        self.refresh()

    def _select_scope(self,ubigeo):
        from .master_contract import validate_field
        validate_field('ubigeo',ubigeo)
        if ubigeo!=self.scope:self.scope=ubigeo;self._dirty=True

    def _scope_queries(self):
        entities='SELECT id FROM entities WHERE ubigeo=?'
        district_versions='SELECT v.id FROM versions v JOIN sources s ON s.id=v.source_id WHERE s.ubigeo=?'
        people='SELECT person_id FROM relationships WHERE entity_id IN ('+entities+') AND person_id IS NOT NULL'
        version_scope='id IN ('+district_versions+') OR id IN (SELECT source_version FROM people WHERE id IN ('+people+'))'
        source_scope='ubigeo=? OR id IN (SELECT source_id FROM versions WHERE '+version_scope+')'
        predicates={
            'meta':'1=1',
            'projects':'ubigeo=? OR id IN (SELECT project_id FROM sources WHERE '+source_scope+')',
            'sources':source_scope,'versions':version_scope,'entities':'ubigeo=?',
            'people':'id IN ('+people+')',
            'contributions':'version_id IN ('+district_versions+')',
            'identities':'entity_id IN ('+entities+')',
            'selections':'entity_id IN ('+entities+')',
            'relationships':'entity_id IN ('+entities+')',
            'media':'entity_id IN ('+entities+')','boundary_segments':'entity_id IN ('+entities+')',
            'registral_acts':'entity_id IN ('+entities+')',
            'attribute_definitions':'source_version IS NULL OR source_version IN ('+district_versions+')',
            'administrative_areas':'source_version IS NULL OR source_version IN ('+district_versions+')',
            'addresses':'entity_id IN ('+entities+') OR source_version IN ('+district_versions+')',
            'property_observations':'entity_id IN ('+entities+') OR source_version IN ('+district_versions+')',
            'external_identifiers':'entity_id IN ('+entities+') OR source_version IN ('+district_versions+')',
            'listings':'entity_id IN ('+entities+') OR source_version IN ('+district_versions+')',
            'listing_observations':'source_version IN ('+district_versions+')',
            'transactions':'entity_id IN ('+entities+') OR source_version IN ('+district_versions+')',
            'organizations':'source_version IN ('+district_versions+')',
            'activities':'entity_id IN ('+entities+') OR source_version IN ('+district_versions+')',
            'visits':'entity_id IN ('+entities+') OR source_version IN ('+district_versions+')',
            'developments':'source_version IN ('+district_versions+')',
            'development_lots':'entity_id IN ('+entities+') OR source_version IN ('+district_versions+')',
            'development_stages':'source_version IN ('+district_versions+')',
            'environment_features':'ubigeo=? OR source_version IN ('+district_versions+')',
            'coverage_records':'ubigeo=? OR source_version IN ('+district_versions+')',
            'catalog_review_status':'source_version IN ('+district_versions+')',
            'catalog_review_events':'source_version IN ('+district_versions+')',
            'plan_workspace':'scope_ubigeo=?', 'plan_notes':'scope_ubigeo=?',
            'current_attributes':'entity_id IN ('+entities+')',
            'zones':'source_version IS NULL OR source_version IN ('+district_versions+')',
            'journal':"json_extract(details_json,'$.scope_ubigeo')=? OR (json_extract(details_json,'$.scope_ubigeo') IS NULL AND ("
                      "json_extract(details_json,'$.version_id') IN ("+district_versions+") OR "
                      "json_extract(details_json,'$.project_id') IN (SELECT id FROM projects WHERE ubigeo=?)))"
        }
        return {table:('SELECT * FROM '+table+' WHERE '+predicates[table]+
                       ' ORDER BY '+','.join(PAGE_KEYS.get(table,keys)),
                       [self.scope]*predicates[table].count('?')) for table,keys in TABLES.items()}

    def _rows(self):
        return {table:[tuple(row) for row in self.db.execute('SELECT * FROM '+table)] for table in TABLES}

    def refresh(self):
        with self.lock:
            revision=self.gateway.revision()
            if not self._dirty and revision==self.revision:return
            rows={};total=0;size=0
            queries=self._scope_queries()
            first_pages=None
            if hasattr(self.gateway,'read_many'):
                first_pages={}
                names=list(TABLES)
                for offset in range(0,len(names),20):
                    batch=names[offset:offset+20]
                    results=self.gateway.read_many([
                        {'sql':queries[name][0]+' LIMIT 1000','params':queries[name][1]}
                        for name in batch])
                    first_pages.update(zip(batch,results))
            for table,keys in TABLES.items():
                rows[table]=[];cursor=None
                page_keys=PAGE_KEYS.get(table,keys)
                while True:
                    if first_pages is not None and cursor is None:
                        page=first_pages[table]
                    else:
                        sql,params=_page_query(queries[table][0],page_keys,cursor)
                        page=self.gateway.read(sql+' LIMIT 1000',
                                               [*queries[table][1],*params])
                    total+=len(page);size+=len(encoded(page).encode())
                    if total > MAX_SCOPE_ROWS or size > MAX_SCOPE_BYTES:
                        raise StorageError('El ámbito excede el límite de edición en memoria; requiere particionar la carga antes de continuar.')
                    rows[table].extend(page)
                    if len(page)<1000:break
                    cursor=tuple(page[-1][key] for key in page_keys)
            # Optimized page order is a transport detail. Restore the original
            # primary-key order inside the working copy so visible ordering and
            # every calculation stay byte-for-byte compatible with prior loads.
            for table,keys in TABLES.items():
                rows[table].sort(key=lambda row, keys=keys:
                                 tuple(row[key] for key in keys))
            if self.gateway.revision()!=revision:
                raise Conflict('El maestro cambió durante la lectura; actualiza para cargar una revisión coherente.')
            with self.db:
                for table in reversed(TABLES):self.db.execute('DELETE FROM '+table)
                for table in TABLES:
                    names=[r[1] for r in self.db.execute('PRAGMA table_info('+table+')')]
                    self.db.executemany('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in names)+')',
                                        ([row[name] for name in names] for row in rows[table]))
            self._dirty=False
            self._journal_state=self._snapshot()

    def _hydrate_people(self,version_id):
        row=self.db.execute('SELECT payload FROM versions WHERE id=?',(version_id,)).fetchone()
        if not row:return
        ids=[]
        for owner in json.loads(row[0]).get('people',[]):
            if owner.get('row') is not None and not owner.get('relationship_status') and owner.get('document_type') and owner.get('document_number'):
                ids.append(str(uuid.uuid5(uuid.NAMESPACE_URL,encoded(['person-document',owner['document_type'],owner['document_number']]))))
        if not ids:return
        people='SELECT id FROM people WHERE id IN (SELECT value FROM json_each(?))'
        versions='SELECT source_version FROM people WHERE id IN ('+people+')'
        sources='SELECT source_id FROM versions WHERE id IN ('+versions+')'
        queries={'projects':'SELECT * FROM projects WHERE id IN (SELECT project_id FROM sources WHERE id IN ('+sources+'))',
                 'sources':'SELECT * FROM sources WHERE id IN ('+sources+')',
                 'versions':'SELECT * FROM versions WHERE id IN ('+versions+')','people':'SELECT * FROM people WHERE id IN ('+people+')'}
        with self.db:
            for table,sql in queries.items():
                rows=self.gateway.read(sql,[encoded(ids)])
                columns=[r[1] for r in self.db.execute('PRAGMA table_info('+table+')')]
                self.db.executemany('INSERT OR IGNORE INTO '+table+' VALUES ('+','.join('?' for _ in columns)+')',
                                    ([row[key] for key in columns] for row in rows))

    def _mutate(self,method,*args,_incoming_version=None,**kwargs):
        with self.lock:
            self.refresh()
            if _incoming_version:self._hydrate_people(_incoming_version)
            revision=self.revision;before=self._rows()
            try:
                result=method(*args,**kwargs)
                after=self._rows();changes=[]
                for table,keys in TABLES.items():
                    names=[r[1] for r in self.db.execute('PRAGMA table_info('+table+')')]
                    positions=[names.index(key) for key in keys]
                    key=lambda row:tuple(row[i] for i in positions)
                    old={key(row):row for row in before[table]};new={key(row):row for row in after[table]}
                    upserts=[row for k,row in new.items() if old.get(k)!=row]
                    deletes=[k for k in old if k not in new]
                    if upserts or deletes:changes.append({'table':table,'upserts':upserts,'deletes':deletes})
                if not changes:return result
                payload={'action':'commit','id':str(uuid.uuid4()),'revision':revision,'changes':changes,'result':result}
                confirmed=self.gateway.call(payload)
                return confirmed['result']
            except Exception:
                self._dirty=True
                raise

    def project(self,*args,**kwargs):
        def update():
            if self.db.execute('SELECT 1 FROM projects WHERE id=?',(args[0],)).fetchone():return {'unchanged':True}
            super(D1Store,self).project(*args,**kwargs)
            return {'revision':self._journal('project','sistema','Registrar proyecto',{'project_id':args[0]})}
        with self.lock:
            self._select_scope(args[2]);return self._mutate(update)

    def stage(self,*args,**kwargs):
        with self.lock:
            payload=args[0] if args else kwargs.get('payload')
            if not isinstance(payload,dict) or not isinstance(payload.get('source'),dict):raise ValueError('Indica fuente y versión.')
            self._select_scope(payload['source'].get('ubigeo'))
            return self._mutate(super().stage,*args,**kwargs)
    def review_catalog(self,*args,**kwargs):
        with self.lock:
            return self._mutate(super().review_catalog,*args,**kwargs)
    def _select_plan_scope(self,source_version,scope_ubigeo):
        from .master_contract import validate_field
        if source_version:
            rows=self.gateway.read('''SELECT s.ubigeo FROM versions v
                JOIN sources s ON s.id=v.source_id WHERE v.id=?''',[source_version])
            if not rows:raise ValueError('La versión del plano no existe.')
            scope_ubigeo=rows[0]['ubigeo']
        validate_field('ubigeo',scope_ubigeo)
        self._select_scope(scope_ubigeo)
    def update_plan_title(self,*args,**kwargs):
        with self.lock:
            values=list(args)
            key=values[0] if values else kwargs.get('document_key')
            dtype=values[1] if len(values)>1 else kwargs.get('document_type')
            version=values[2] if len(values)>2 else kwargs.get('source_version')
            scope=values[3] if len(values)>3 else kwargs.get('scope_ubigeo')
            self._select_plan_scope(version if dtype in ('source','source-version') else None,scope)
            return self._mutate(super().update_plan_title,*args,**kwargs)
    def add_plan_note(self,*args,**kwargs):
        with self.lock:
            dtype=args[1] if len(args)>1 else kwargs.get('document_type')
            version=args[2] if len(args)>2 else kwargs.get('source_version')
            scope=args[3] if len(args)>3 else kwargs.get('scope_ubigeo')
            self._select_plan_scope(version if dtype in ('source','source-version') else None,scope)
            return self._mutate(super().add_plan_note,*args,**kwargs)
    def plan_annotations(self,document_keys):
        keys=list(dict.fromkeys(str(key) for key in document_keys if key))
        if not keys or len(keys)>200:raise ValueError('Consulta de notas fuera de límite.')
        return {row['document_key']:row for row in self.gateway.read(
            '''SELECT w.document_key,w.document_type,w.source_version,w.scope_ubigeo,
                      w.display_title,w.updated_at,w.updated_by,w.revision,
                      (SELECT count(*) FROM plan_notes n WHERE n.document_key=w.document_key) AS note_count
               FROM plan_workspace w WHERE w.document_key IN (SELECT value FROM json_each(?))''',
            [encoded(keys)])}
    def plan_notes_for(self,document_key):
        return self.gateway.read('''SELECT id,document_key,note,created_at,actor,revision
            FROM plan_notes WHERE document_key=? ORDER BY created_at DESC LIMIT 500''',
            [document_key])
    def apply(self,*args,**kwargs):
        with self.lock:
            plan=args[0] if args else kwargs.get('plan')
            if not isinstance(plan,dict) or not isinstance(plan.get('scope'),dict):raise ValueError('Indica el ámbito del cambio.')
            self._select_scope(plan['scope'].get('ubigeo'))
            return self._mutate(super().apply,*args,_incoming_version=plan.get('version_id') if plan.get('mode')!='withdraw_source' else None,**kwargs)
    def restore(self,revision,*args,**kwargs):
        with self.lock:
            rows=self.gateway.read('''SELECT COALESCE(json_extract(j.details_json,'$.scope_ubigeo'),s.ubigeo,p.ubigeo) ubigeo
                FROM journal j LEFT JOIN versions v ON v.id=json_extract(j.details_json,'$.version_id')
                LEFT JOIN sources s ON s.id=v.source_id LEFT JOIN projects p ON p.id=json_extract(j.details_json,'$.project_id')
                WHERE j.revision=?''',[revision])
            if not rows or not rows[0]['ubigeo']:raise ValueError('Revisión no disponible para este ámbito.')
            self._select_scope(rows[0]['ubigeo'])
            return self._mutate(super().restore,revision,*args,**kwargs)
    def preview(self,*args,**kwargs):
        with self.lock:
            plan=args[0] if args else kwargs.get('plan')
            if not isinstance(plan,dict) or not isinstance(plan.get('scope'),dict):raise ValueError('Indica el ámbito del cambio.')
            self._select_scope(plan['scope'].get('ubigeo'))
            self.refresh();return super().preview(*args,**kwargs)
    def summary(self,ubigeo=None):
        with self.lock:
            if ubigeo:self._select_scope(ubigeo)
            self.refresh();value=super().summary();value['storage']='d1';return value
    def records(self,*args,**kwargs):
        query,params=self._records_query(*args,**kwargs)
        return self.gateway.read(query,params)
    def collection(self,*args,**kwargs):
        with self.lock:
            ubigeo = args[0] if args else kwargs.get('ubigeo')
            kind = args[1] if len(args) > 1 else kwargs.get('kind')
            revision = kwargs.get('revision')
            # Publik map reads are bounded keyset queries. Do not materialize
            # the mutable authoring scope, whose migration journal can be much
            # larger than one viewport/district payload.
            return D1ReadModel(self.gateway).collection(
                ubigeo, kind, revision=revision)
    def active_districts(self):
        return [r['ubigeo'] for r in self.gateway.read("""SELECT DISTINCT e.ubigeo FROM entities e
            JOIN selections s ON s.entity_id=e.id WHERE e.kind IN ('lote','manzana') AND s.field='$geometry'""")]
    def entity(self,*args):
        with self.lock:
            rows=self.gateway.read('SELECT ubigeo FROM entities WHERE id=?',[args[0]])
            if not rows:raise ValueError('Inmueble no disponible.')
            self._select_scope(rows[0]['ubigeo']);self.refresh();return super().entity(*args)
    def medium(self,*args):
        with self.lock:
            rows=self.gateway.read('SELECT e.ubigeo FROM media m JOIN entities e ON e.id=m.entity_id WHERE m.id=?',[args[0]])
            if not rows:raise ValueError('Archivo no disponible.')
            self._select_scope(rows[0]['ubigeo']);self.refresh();return super().medium(*args)

    def version_payload(self,version_id):
        rows=self.gateway.read('SELECT payload FROM versions WHERE id=?',[version_id])
        return json.loads(rows[0]['payload']) if rows else None
