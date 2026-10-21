"""Reversible, field-level master composition. Preview storage is strictly RAM.

Original versions are immutable. Selections reference observations; withdrawing
a source never deletes entities, relationships, documents or source versions.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from threading import RLock
import uuid

from . import master_contract as contract


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(value, label='Identificador'):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}', value):
        raise ValueError(label + ' no válido.')
    return value


class Conflict(ValueError):
    pass


def geometry(value, geographic):
    if not isinstance(value, dict) or value.get('type') not in ('Polygon', 'MultiPolygon'):
        raise ValueError('Se requiere una geometría poligonal.')
    polygons = [value.get('coordinates')] if value['type'] == 'Polygon' else value.get('coordinates')
    if not isinstance(polygons, list) or not polygons:
        raise ValueError('Geometría vacía.')
    for rings in polygons:
        if not isinstance(rings, list) or not rings:
            raise ValueError('Polígono vacío.')
        for ring in rings:
            if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError('El contorno debe estar cerrado.')
            for p in ring:
                if (not isinstance(p, (list, tuple)) or len(p) != 2
                        or any(type(n) not in (int, float) or not math.isfinite(n) for n in p)):
                    raise ValueError('Coordenadas no válidas.')
                if geographic and not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90):
                    raise ValueError('Las coordenadas no corresponden a WGS84.')
    from shapely.geometry import shape
    shape_value = shape(value)
    if shape_value.is_empty or not shape_value.is_valid or shape_value.area <= 0:
        raise ValueError('El polígono requiere revisión topológica.')


class MasterStore:
    def __init__(self):
        self.lock = RLock()
        self.db = sqlite3.connect(':memory:', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(Path(__file__).with_name('master_schema.sql').read_text(encoding='utf8'))
        self.columns = {r[1] for r in self.db.execute('PRAGMA table_info(current_attributes)')} - {'entity_id'}
        self._journal_state={'selections':[],'roles':[]}

    @property
    def revision(self):
        return int(self.db.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])

    def _expected(self, value):
        if type(value) is not int or value != self.revision:
            raise Conflict('El maestro cambió. Actualiza y revisa otra vez la comparación.')

    def _snapshot(self):
        scope=getattr(self,'scope',None)
        return {'selections': [list(r) for r in self.db.execute(
            'SELECT entity_id,field,contribution_id FROM selections ORDER BY entity_id,field')],
            'roles': [list(r) for r in self.db.execute('SELECT id,role FROM sources '+('WHERE ubigeo=? ' if scope else '')+'ORDER BY id',
                                                     (scope,) if scope else ())]}

    def _journal(self, operation, actor, reason, details):
        if getattr(self,'scope',None):details={**details,'scope_ubigeo':self.scope}
        snapshot=self._snapshot()
        before={(r[0],r[1]):r[2] for r in self._journal_state['selections']}
        after={(r[0],r[1]):r[2] for r in snapshot['selections']}
        roles_before=dict(self._journal_state['roles']);roles_after=dict(snapshot['roles'])
        delta={'format':2,'selection_changes':[[*key,after.get(key)] for key in sorted(before.keys()|after.keys())
                                             if before.get(key)!=after.get(key)],
               'role_changes':[[key,value] for key,value in roles_after.items() if roles_before.get(key)!=value]}
        revision = self.revision + 1
        self.db.execute("UPDATE meta SET value=? WHERE key='revision'", (str(revision),))
        self.db.execute('INSERT INTO journal VALUES (?,?,?,?,?,?,?)',
                        (revision, operation, str(actor)[:160], now(), reason[:1000],
                         encoded(details), encoded(delta)))
        self._journal_state=snapshot
        return revision

    def _historical_selection(self,revision):
        selections,roles={},{}
        for row in self.db.execute('SELECT snapshot_json FROM journal WHERE revision<=? ORDER BY revision',(revision,)):
            snapshot=json.loads(row[0])
            if snapshot.get('format')==2:
                for eid,field,contribution in snapshot['selection_changes']:
                    if contribution is None:selections.pop((eid,field),None)
                    else:selections[(eid,field)]=contribution
                roles.update(snapshot['role_changes'])
            else:
                # Read existing immutable snapshots created by the first revision.
                selections={(eid,field):value for eid,field,value in snapshot['selections']}
                roles=dict(snapshot['roles'])
        return {'selections':[[eid,field,value] for (eid,field),value in selections.items()],
                'roles':list(roles.items())}

    def project(self, project_id, name, ubigeo, expected_sheets):
        identifier(project_id)
        contract.validate_field('ubigeo', ubigeo)
        if type(expected_sheets) is not int or not 1 <= expected_sheets <= 10000:
            raise ValueError('Cantidad prevista de láminas no válida.')
        with self.lock, self.db:
            self.db.execute('INSERT INTO projects VALUES (?,?,?,?,?)',
                            (project_id, str(name)[:300], 'PE', ubigeo, expected_sheets))

    def stage(self, payload, expected_revision, actor):
        """Register one immutable source version; no observation becomes current."""
        if not isinstance(payload, dict):
            raise ValueError('La versión debe ser un objeto.')
        value = deepcopy(payload)
        source, version = value.get('source'), value.get('version')
        if not isinstance(source, dict) or not isinstance(version, dict):
            raise ValueError('Indica fuente y versión.')
        sid, vid = identifier(source.get('id')), identifier(version.get('id'))
        district = contract.validate_field('ubigeo', source.get('ubigeo'))
        if not isinstance(source.get('name'), str) or not source['name'].strip():
            raise ValueError('La fuente necesita un nombre.')
        if not isinstance(version.get('label'), str) or not version['label'].strip():
            raise ValueError('La versión necesita una etiqueta.')
        geo = version.get('georeferencing', {})
        if not isinstance(geo, dict) or geo.get('status') not in ('pending', 'verified'):
            raise ValueError('Declara el estado de georreferenciación.')
        verified = geo['status'] == 'verified'
        if verified and (version.get('crs') != 'EPSG:4326' or not geo.get('method') or not geo.get('evidence')):
            raise ValueError('La posición verificada necesita método, evidencia y coordenadas WGS84.')
        items = value.get('features', [])
        for key in ('people','media','relationships','boundary_segments','registral_acts'):
            rows=value.get(key,[])
            if not isinstance(rows,list) or len(rows)>30000 or any(not isinstance(row,dict) for row in rows):
                raise ValueError('Relaciones o documentos no válidos: '+key)
        if not isinstance(items, list) or len(items) > 30000:
            raise ValueError('La versión admite hasta 30.000 elementos; divide fuentes mayores.')
        seen, observations = set(), []
        for item in items:
            if not isinstance(item, dict) or item.get('kind') not in contract.KINDS:
                raise ValueError('Tipo de elemento no válido.')
            fid, kind = identifier(item.get('id')), item['kind']
            if (kind, fid) in seen:
                raise ValueError('Hay identificadores de elemento repetidos en la versión.')
            seen.add((kind, fid))
            values = item.get('fields', {})
            if not isinstance(values, dict) or not isinstance(item.get('provenance', {}), dict):
                raise ValueError('Campos o procedencia no válidos.')
            for key, val in values.items():
                if val is None:
                    continue  # Missing observations never erase a previously known value.
                contract.validate_field(key, val)
                if key == 'ubigeo' and val != district or key == 'country_code' and val != 'PE':
                    raise ValueError('El elemento no corresponde al ámbito de la fuente.')
                evidence = item.get('provenance', {}).get(key, {'status': 'declared', 'field': key})
                observations.append((fid, kind, key, val, evidence))
            if item.get('geometry') is not None:
                geometry(item['geometry'], version.get('crs') == 'EPSG:4326')
                observations.append((fid, kind, '$geometry', item['geometry'], geo))
        digest = hashlib.sha256(encoded(value).encode()).hexdigest()
        with self.lock, self.db:
            self._expected(expected_revision)
            prior = self.db.execute('SELECT digest FROM versions WHERE id=?', (vid,)).fetchone()
            if prior:
                if prior[0] != digest:
                    raise Conflict('La versión ya existe con otro contenido; registra una versión nueva.')
                return {'revision': self.revision, 'version_id': vid, 'unchanged': True}
            existing = self.db.execute('SELECT * FROM sources WHERE id=?', (sid,)).fetchone()
            if existing and (existing['ubigeo'] != district or existing['project_id'] != source.get('project_id')
                             or existing['sheet_code'] != source.get('sheet_code')):
                raise ValueError('Una fuente no puede cambiar de distrito, proyecto o lámina.')
            project_id = source.get('project_id')
            if project_id:
                project = self.db.execute('SELECT ubigeo FROM projects WHERE id=?', (project_id,)).fetchone()
                if not project or project[0] != district:
                    raise ValueError('El proyecto no corresponde al distrito.')
            if not existing:
                role = source.get('role', 'candidate')
                if role not in ('candidate', 'backup'):
                    raise ValueError('Las fuentes nuevas ingresan como candidatas o respaldo.')
                self.db.execute('INSERT INTO sources VALUES (?,?,?,?,?,?)',
                                (sid, project_id, source['name'][:300], district, source.get('sheet_code'), role))
            if self.db.execute('SELECT 1 FROM versions WHERE source_id=? AND label=?', (sid, version['label'])).fetchone():
                raise Conflict('La etiqueta ya está usada; registra una nueva versión.')
            original = version.get('original') or {}
            self.db.execute('INSERT INTO versions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                            (vid, sid, version['label'], version.get('source_date'), version.get('crs'),
                             encoded(geo), original.get('name'), original.get('sha256'), digest, now(),
                             str(actor)[:160], encoded(value),))
            for fid, kind, key, val, evidence in observations:
                oid = str(uuid.uuid5(uuid.NAMESPACE_URL, encoded([vid, kind, fid, key])))
                self.db.execute('INSERT INTO contributions VALUES (?,?,?,?,?,?,?)',
                                (oid, vid, fid, kind, key, encoded(val), encoded(evidence)))
            revision = self._journal('stage', actor, 'Versión candidata; sin aplicar al maestro.', {'version_id': vid})
            return {'revision': revision, 'version_id': vid, 'observations': len(observations)}

    def _resolve(self, row, plan):
        key = row['layer'] + ':' + row['source_feature_id']
        target = plan.get('identity_map', {}).get(key)
        if target:
            identifier(target, 'Identificador maestro')
            bound = self.db.execute('SELECT entity_id FROM identities WHERE version_id=? AND layer=? AND source_feature_id=?',
                                    (row['version_id'],row['layer'],row['source_feature_id'])).fetchone()
            if bound and bound[0] != target:
                raise Conflict('Esta versión ya está vinculada a otra identidad; registra una revisión nueva para corregirla.')
            existing = self.db.execute('SELECT * FROM entities WHERE id=?', (target,)).fetchone()
            if not existing or existing['kind'] != row['layer'] or existing['ubigeo'] != plan['scope']['ubigeo']:
                raise ValueError('La correspondencia no pertenece al mismo distrito y tipo: ' + key)
            return target, False
        known = self.db.execute('''SELECT DISTINCT i.entity_id FROM identities i
            JOIN versions v ON v.id=i.version_id WHERE v.source_id=? AND i.layer=? AND i.source_feature_id=?''',
            (row['source_id'], row['layer'], row['source_feature_id'])).fetchall()
        if len(known) > 1:
            raise ValueError('La identidad requiere revisión: ' + key)
        if known:
            return known[0][0], False
        if plan['mode'] == 'replace_fields':
            raise ValueError('Relaciona cada elemento con su inmueble antes de sustituir campos: ' + key)
        return str(uuid.uuid5(uuid.NAMESPACE_URL, encoded(['catastro-maestro', 'PE', row['source_id'], row['layer'], row['source_feature_id']]))), True

    def _plan(self, plan):
        if not isinstance(plan, dict) or not isinstance(plan.get('scope'), dict):
            raise ValueError('Indica el ámbito del cambio.')
        self._expected(plan.get('revision'))
        mode = plan.get('mode')
        if mode not in ('fill', 'replace_fields', 'replace_scope', 'withdraw_source'):
            raise ValueError('Operación no válida.')
        scope = plan['scope']
        district = contract.validate_field('ubigeo', scope.get('ubigeo'))
        if scope.get('kind') not in contract.KINDS:
            raise ValueError('Elige una capa para delimitar el cambio.')
        if not isinstance(plan.get('reason'), str) or not plan['reason'].strip():
            raise ValueError('Describe el motivo del cambio.')
        if not isinstance(plan.get('identity_map', {}), dict):
            raise ValueError('Correspondencias no válidas.')
        selected_fields = plan.get('fields', [])
        if not isinstance(selected_fields, list) or len(set(selected_fields)) != len(selected_fields):
            raise ValueError('Selección de campos no válida.')
        if any(f != '$geometry' and f not in {d['key'] for d in contract.fields()} for f in selected_fields):
            raise ValueError('Hay campos desconocidos.')
        if mode == 'replace_fields' and not selected_fields:
            raise ValueError('Elige qué campos sustituir.')
        targets = {r['id'] for r in self.db.execute('SELECT id FROM entities WHERE ubigeo=? AND kind=?',
                                                   (district, scope['kind']))}
        if 'entity_ids' in scope:
            if not isinstance(scope['entity_ids'], list) or not set(scope['entity_ids']).issubset(targets):
                raise ValueError('El ámbito contiene entidades ajenas o desconocidas.')
            targets.intersection_update(scope['entity_ids'])
        if scope.get('sector'):
            in_sector = {r[0] for r in self.db.execute('SELECT entity_id FROM current_attributes WHERE ubigeo=? AND sector=?',
                                                      (district, scope['sector']))}
            targets.intersection_update(in_sector)
        current = {(r['entity_id'], r['field']): r['contribution_id'] for r in self.db.execute('SELECT * FROM selections')}
        changes, bindings, entities, skipped = {}, {}, {}, 0
        if mode in ('replace_scope', 'withdraw_source'):
            if mode == 'withdraw_source':
                sid = identifier(plan.get('source_id'))
                source = self.db.execute('SELECT ubigeo FROM sources WHERE id=?', (sid,)).fetchone()
                if not source or source[0] != district:
                    raise ValueError('La fuente no corresponde al ámbito.')
                eligible = {r[0] for r in self.db.execute('''SELECT c.id FROM contributions c
                    JOIN versions v ON v.id=c.version_id WHERE v.source_id=?''', (sid,))}
            for key, oid in current.items():
                if key[0] in targets and (not selected_fields or key[1] in selected_fields):
                    if mode != 'withdraw_source' or oid in eligible:
                        changes[key] = None
        if mode != 'withdraw_source':
            vid = identifier(plan.get('version_id'))
            version = self.db.execute('''SELECT v.*,s.ubigeo,s.id AS source_id FROM versions v
                JOIN sources s ON s.id=v.source_id WHERE v.id=?''', (vid,)).fetchone()
            if not version or version['ubigeo'] != district:
                raise ValueError('La versión no corresponde al ámbito.')
            observations = self.db.execute('''SELECT c.*,v.source_id FROM contributions c
                JOIN versions v ON v.id=c.version_id WHERE c.version_id=? AND c.layer=?''', (vid, scope['kind'])).fetchall()
            if not observations:
                raise ValueError('Esta versión todavía no contiene elementos de la capa elegida.')
            mapping = plan.get('identity_map', {})
            valid_keys = {r['layer'] + ':' + r['source_feature_id'] for r in observations}
            if not set(mapping).issubset(valid_keys):
                raise ValueError('La correspondencia contiene elementos ausentes de la capa.')
            reverse = {}
            for row in observations:
                if selected_fields and row['field'] not in selected_fields:
                    continue
                eid, is_new = self._resolve(row, plan)
                if is_new and 'entity_ids' in scope:
                    raise ValueError('Un ámbito de inmuebles concretos requiere correspondencias; no puede incorporar elementos sin relacionar.')
                if ('entity_ids' in scope or scope.get('sector')) and not is_new and eid not in targets:
                    raise ValueError('Una correspondencia queda fuera del ámbito seleccionado.')
                if scope.get('sector') and is_new:
                    sector = next((json.loads(r['value_json']) for r in observations if
                        r['source_feature_id'] == row['source_feature_id'] and r['field'] == 'sector'), None)
                    if sector != scope['sector']:
                        raise ValueError('Un elemento nuevo no acredita el sector seleccionado.')
                origin = row['layer'] + ':' + row['source_feature_id']
                if eid in reverse and reverse[eid] != origin:
                    raise ValueError('No fusiones dos elementos en una identidad. Revisa subdivisiones/acumulaciones.')
                reverse[eid] = origin
                if row['field'] == '$geometry':
                    geo = json.loads(version['georeferencing'])
                    if geo['status'] != 'verified' or version['crs'] != 'EPSG:4326':
                        raise ValueError('La geometría sigue pendiente de georreferenciación; no puede activarse.')
                if mode == 'fill' and (eid, row['field']) in current:
                    skipped += 1
                    continue
                if mode == 'replace_fields' and is_new:
                    raise ValueError('Sustituir campos requiere entidades existentes.')
                if is_new:
                    entities[eid] = row['layer']
                bindings[(vid, row['layer'], row['source_feature_id'])] = eid
                changes[(eid, row['field'])] = row['id']
        changes = {key: val for key, val in changes.items() if current.get(key) != val}
        after = dict(current)
        for key, val in changes.items():
            if val is None:
                after.pop(key, None)
            else:
                after[key] = val
        retiring = sorted(eid for eid in targets if (eid, '$geometry') in current and (eid, '$geometry') not in after)
        token = hashlib.sha256(encoded({'plan': plan, 'changes': sorted((list(k),v) for k,v in changes.items())}).encode()).hexdigest()
        summary = {'revision': self.revision, 'token': token, 'changed_fields': len(changes),
                   'affected_entities': len({key[0] for key in changes}), 'new_entities': len(entities),
                   'geometry_changes': sum(key[1] == '$geometry' for key in changes),
                   'without_geometry': retiring, 'preserved_existing_fields': skipped,
                   'details': [{'entity_id': key[0], 'field': key[1],
                                'before': self._value(current.get(key)), 'after': self._value(val)}
                               for key, val in list(changes.items())[:150]],
                   'details_truncated': len(changes) > 150}
        return summary, changes, bindings, entities

    def _value(self, oid):
        if oid is None:
            return None
        row = self.db.execute('SELECT field,value_json,version_id FROM contributions WHERE id=?', (oid,)).fetchone()
        return {'version_id': row['version_id'], 'value': 'Geometría poligonal' if row['field'] == '$geometry'
                else json.loads(row['value_json'])}

    def preview(self, plan):
        with self.lock:
            return self._plan(plan)[0]

    def apply(self, plan, token, actor):
        with self.lock, self.db:
            summary, changes, bindings, entities = self._plan(plan)
            if token != summary['token']:
                raise Conflict('La comparación no corresponde a este cambio; vuelve a previsualizar.')
            if not changes:
                return {**summary, 'unchanged': True}
            for eid, kind in entities.items():
                self.db.execute('INSERT OR IGNORE INTO entities VALUES (?,?,?,?,?)',
                                (eid, kind, 'PE', plan['scope']['ubigeo'], now()))
            for key, eid in bindings.items():
                self.db.execute('INSERT OR REPLACE INTO identities VALUES (?,?,?,?)', (*key, eid))
            for (eid, field), oid in changes.items():
                if oid is None:
                    self.db.execute('DELETE FROM selections WHERE entity_id=? AND field=?', (eid, field))
                else:
                    self.db.execute('INSERT OR REPLACE INTO selections VALUES (?,?,?)', (eid, field, oid))
            if plan['mode'] != 'withdraw_source':
                self.db.execute("UPDATE sources SET role='contributing' WHERE id=(SELECT source_id FROM versions WHERE id=?)",
                                (plan['version_id'],))
                self._links(plan['version_id'])
            self._project({key[0] for key in changes})
            summary['revision'] = self._journal(plan['mode'], actor, plan['reason'],
                                                {'plan': plan, 'summary': summary})
            return summary

    def _links(self, version_id):
        """Append available documentary links; geometry changes never erase them."""
        payload = json.loads(self.db.execute('SELECT payload FROM versions WHERE id=?', (version_id,)).fetchone()[0])
        identities = {r['layer'] + ':' + r['source_feature_id']: r['entity_id'] for r in self.db.execute(
            'SELECT * FROM identities WHERE version_id=?', (version_id,))}
        def uid(*parts):
            return str(uuid.uuid5(uuid.NAMESPACE_URL, encoded(list(parts))))
        for index, owner in enumerate(payload.get('people', [])):
            record=str(owner.get('source_record_id', ''))
            eid = identities.get('unidad:' + record) or identities.get('registro_documental:' + record)
            if not eid or not owner.get('name'):
                continue
            dtype, number = owner.get('document_type'), owner.get('document_number')
            aligned = owner.get('row') is not None and not owner.get('relationship_status')
            pid = uid('person-document',dtype,number) if aligned and dtype and number else uid('person-observation',version_id,index)
            previous = self.db.execute('SELECT name FROM people WHERE id=?', (pid,)).fetchone()
            details = {**owner, 'document_name_conflict': bool(previous and previous[0] != owner['name'])}
            self.db.execute('INSERT OR IGNORE INTO people VALUES (?,?,?,?,?)',
                            (pid, owner['name'], dtype if aligned else None, number if aligned else None, version_id))
            self.db.execute('INSERT OR IGNORE INTO relationships VALUES (?,?,?,?,?,?,?)',
                            (uid(version_id,'owner',index),eid,None,pid,'titular_segun_documento',encoded(details),version_id))
        for index, relation in enumerate(payload.get('relationships', [])):
            eid, target = identities.get(relation.get('from')), identities.get(relation.get('to'))
            if eid and target:
                self.db.execute('INSERT OR IGNORE INTO relationships VALUES (?,?,?,?,?,?,?)',
                    (uid(version_id,'relation',index),eid,target,None,relation['kind'],encoded(relation),version_id))
        for index, item in enumerate(payload.get('media', [])):
            eid = identities.get(item.get('target'))
            if eid and item.get('object_key') and item.get('kind'):
                self.db.execute('INSERT OR IGNORE INTO media VALUES (?,?,?,?,?,?,?,?)',
                    (uid(version_id,'media',index),eid,item['kind'],item['object_key'],item.get('sha256'),
                     item.get('observed_at'),version_id,encoded(item)))
        for index,item in enumerate(payload.get('boundary_segments',[])):
            eid=identities.get(item.get('target'))
            if not eid:continue
            if item.get('side','unknown') not in ('front','back','left','right','other','unknown'):
                raise ValueError('Clasificación de lindero no válida.')
            length=item.get('length_m')
            if length is not None and (type(length) not in (float,int) or not math.isfinite(length) or length<0):
                raise ValueError('Longitud de lindero no válida.')
            self.db.execute('INSERT OR IGNORE INTO boundary_segments VALUES (?,?,?,?,?,?,?)',
                (uid(version_id,'boundary',index),eid,item.get('side','unknown'),length,
                 encoded(item.get('geometry')) if item.get('geometry') is not None else None,version_id,encoded(item.get('evidence',{}))))
        for index,item in enumerate(payload.get('registral_acts',[])):
            eid=identities.get(item.get('target'))
            if eid and item.get('kind'):
                self.db.execute('INSERT OR IGNORE INTO registral_acts VALUES (?,?,?,?,?,?,?,?,?)',
                    (uid(version_id,'registral-act',index),eid,item['kind'],item.get('registry_office'),
                     item.get('registry_number'),item.get('registry_seat'),item.get('observed_at'),version_id,encoded(item)))

    def _project(self, entity_ids):
        for eid in entity_ids:
            entity = self.db.execute('SELECT * FROM entities WHERE id=?', (eid,)).fetchone()
            values = {'country_code': entity['country_code'], 'ubigeo': entity['ubigeo']}
            for row in self.db.execute('''SELECT s.field,c.value_json FROM selections s
                JOIN contributions c ON c.id=s.contribution_id WHERE s.entity_id=?''', (eid,)):
                if row['field'] in self.columns:
                    values[row['field']] = json.loads(row['value_json'])
            self.db.execute('DELETE FROM current_attributes WHERE entity_id=?', (eid,))
            columns = ['entity_id', *values]
            self.db.execute('INSERT INTO current_attributes (' + ','.join(columns) + ') VALUES ('
                            + ','.join('?' for _ in columns) + ')', (eid, *values.values()))

    def restore(self, revision, expected_revision, actor, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError('Describe el motivo de la reversión.')
        with self.lock, self.db:
            self._expected(expected_revision)
            row = self.db.execute('SELECT snapshot_json FROM journal WHERE revision=?', (revision,)).fetchone()
            if not row:
                raise ValueError('Revisión no disponible.')
            snapshot = self._historical_selection(revision)
            self.db.execute('DELETE FROM selections')
            self.db.executemany('INSERT INTO selections VALUES (?,?,?)', snapshot['selections'])
            scope=getattr(self,'scope',None)
            self.db.execute("UPDATE sources SET role='candidate' WHERE role='contributing'"+(' AND ubigeo=?' if scope else ''),
                            (scope,) if scope else ())
            self.db.executemany('UPDATE sources SET role=? WHERE id=?', ((role,sid) for sid,role in snapshot['roles']))
            self._project([r[0] for r in self.db.execute('SELECT id FROM entities')])
            return {'revision': self._journal('restore', actor, reason, {'restored_revision': revision})}

    def summary(self):
        with self.lock:
            scope=getattr(self,'scope',None)
            projects = [dict(r) for r in self.db.execute('SELECT * FROM projects'+(' WHERE ubigeo=?' if scope else ''),(scope,) if scope else ())]
            for project in projects:
                project['registered_sheets'] = self.db.execute('''SELECT count(DISTINCT sheet_code) FROM sources
                    WHERE project_id=? AND sheet_code IS NOT NULL''', (project['id'],)).fetchone()[0]
            sources = [dict(r) for r in self.db.execute('SELECT * FROM sources '+('WHERE ubigeo=? ' if scope else '')+'ORDER BY name',(scope,) if scope else ())]
            for source in sources:
                source['versions'] = [dict(r) for r in self.db.execute('''SELECT v.id,v.label,v.source_date,v.crs,
                    v.georeferencing,v.original_name,v.digest,count(DISTINCT c.layer||':'||c.source_feature_id) AS elements
                    FROM versions v LEFT JOIN contributions c ON c.version_id=v.id WHERE v.source_id=? GROUP BY v.id
                    ORDER BY v.created_at''', (source['id'],))]
                for version in source['versions']:
                    version['georeferencing'] = json.loads(version['georeferencing'])
            return {'schema': contract.VERSION, 'revision': self.revision, 'storage': 'memory',
                    'projects': projects, 'sources': sources, 'fields': contract.fields(),
                    'business_categories': contract.BUSINESS_CATEGORIES,
                    'active_entities': self.db.execute("SELECT count(*) FROM selections WHERE field='$geometry'").fetchone()[0],
                    'history': [dict(r) for r in self.db.execute('''SELECT revision,operation,actor,created_at,reason
                        FROM journal ORDER BY revision DESC LIMIT 100''')]}

    def _records_query(self, filters=None):
        filters = filters or {}
        allowed = (set(contract.TEXT_FIELDS) | set(contract.BOOLEAN_FIELDS)) & self.columns
        numeric = set(contract.NUMBER_FIELDS) & self.columns
        allowed |= {prefix+key for key in numeric for prefix in ('min_','max_')}
        allowed.add('owner_document_number')
        if set(filters) - allowed:
            raise ValueError('Filtro no disponible.')
        clauses, parameters = [], []
        for key,value in filters.items():
            if key=='owner_document_number':
                clauses.append('''EXISTS(SELECT 1 FROM relationships r JOIN people p ON p.id=r.person_id
                    WHERE r.entity_id=a.entity_id AND p.document_number=?)''')
                parameters.append(str(value))
            elif key.startswith(('min_','max_')):
                number = float(value)
                if not math.isfinite(number) or number < 0:
                    raise ValueError('Rango numérico no válido.')
                clauses.append('a.' + key[4:] + ('>=?' if key.startswith('min_') else '<=?'))
                parameters.append(number)
            elif key in contract.BOOLEAN_FIELDS:
                if value not in ('true','false','1','0',True,False):
                    raise ValueError('Filtro sí/no no válido.')
                clauses.append('a.' + key + '=?')
                parameters.append(1 if value in ('true','1',True) else 0)
            else:
                clauses.append('a.' + key + '=?')
                parameters.append(value)
        where = ' AND '.join(clauses) or '1=1'
        query='''SELECT a.*,e.kind,
                EXISTS(SELECT 1 FROM selections s WHERE s.entity_id=e.id AND s.field='$geometry') AS has_geometry
                FROM current_attributes a JOIN entities e ON e.id=a.entity_id WHERE ''' + where + ' ORDER BY a.entity_id LIMIT 1000'
        return query,parameters

    def records(self, filters=None):
        query,parameters=self._records_query(filters)
        with self.lock:
            return [dict(r) for r in self.db.execute(query,parameters)]

    def active_districts(self):
        with self.lock:
            return [r[0] for r in self.db.execute("""SELECT DISTINCT e.ubigeo FROM entities e
                JOIN selections s ON s.entity_id=e.id WHERE e.kind IN ('lote','manzana') AND s.field='$geometry'""")]

    def entity(self, entity_id):
        identifier(entity_id)
        with self.lock:
            entity=self.db.execute('SELECT * FROM entities WHERE id=?',(entity_id,)).fetchone()
            if not entity:raise ValueError('Inmueble no disponible.')
            attributes=self.db.execute('SELECT * FROM current_attributes WHERE entity_id=?',(entity_id,)).fetchone()
            owners=[dict(r) for r in self.db.execute('''SELECT p.id,p.name,p.document_type,p.document_number,
                r.kind,r.source_version,r.details_json FROM relationships r JOIN people p ON p.id=r.person_id
                WHERE r.entity_id=? ORDER BY p.name''',(entity_id,))]
            media=[{**dict(r),'url':'/catastro/api/maestro/medios/'+r['id']+'/'} for r in self.db.execute(
                'SELECT id,kind,sha256,observed_at,source_version FROM media WHERE entity_id=?',(entity_id,))]
            related=[dict(r) for r in self.db.execute('''SELECT id,
                CASE WHEN entity_id=? THEN related_entity_id ELSE entity_id END AS related_entity_id,kind,source_version
                FROM relationships WHERE (entity_id=? OR related_entity_id=?) AND related_entity_id IS NOT NULL''',
                (entity_id,entity_id,entity_id))]
            evidence={r['field']:{'version_id':r['version_id'],'evidence':json.loads(r['evidence_json'])}
                for r in self.db.execute('''SELECT s.field,c.version_id,c.evidence_json FROM selections s
                    JOIN contributions c ON c.id=s.contribution_id WHERE s.entity_id=?''',(entity_id,))}
            return {'entity':dict(entity),'attributes':dict(attributes) if attributes else {},'owners':owners,
                    'media':media,'relationships':related,'provenance':evidence,
                    'boundary_segments':[dict(r) for r in self.db.execute('SELECT * FROM boundary_segments WHERE entity_id=?',(entity_id,))],
                    'registral_acts':[dict(r) for r in self.db.execute('SELECT * FROM registral_acts WHERE entity_id=?',(entity_id,))]}

    def medium(self, media_id):
        identifier(media_id)
        with self.lock:
            row=self.db.execute('SELECT * FROM media WHERE id=?',(media_id,)).fetchone()
            if not row:raise ValueError('Archivo no disponible.')
            return dict(row)

    def collection(self, ubigeo, kind):
        contract.validate_field('ubigeo', ubigeo)
        if kind not in contract.KINDS:
            raise ValueError('Capa no válida.')
        with self.lock:
            features = []
            for entity in self.db.execute('SELECT id FROM entities WHERE ubigeo=? AND kind=?', (ubigeo, kind)).fetchall():
                observations = self.db.execute('''SELECT s.field,c.value_json,c.version_id,c.evidence_json FROM selections s
                    JOIN contributions c ON c.id=s.contribution_id WHERE s.entity_id=?''', (entity[0],)).fetchall()
                values = {r['field']: json.loads(r['value_json']) for r in observations}
                shape = values.pop('$geometry', None)
                if shape is not None:
                    features.append({'type':'Feature','id':entity[0],'geometry':shape,'properties':values,
                                     'provenance': {r['field']:{'version_id':r['version_id'],
                                         'evidence':json.loads(r['evidence_json'])} for r in observations}})
            return {'type':'FeatureCollection','features':features,'revision':self.revision,'crs':'EPSG:4326'}
