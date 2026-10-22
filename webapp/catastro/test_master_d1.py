import json
import sqlite3
from pathlib import Path
from unittest.mock import patch
import os
from unittest import TestCase
from .master_d1 import D1Store,TABLES,configuration
from .master_store import Conflict
from .storage import StorageError
from .source_manager import enabled
from .test_master_store import candidate


class GatewayConfigurationTests(TestCase):
    def test_app_service_settings_override_local_secret_file(self):
        values={'CATASTRO_MASTER_GATEWAY_URL':'https://prometeo-catastro-maestro.sistema-propify.workers.dev',
                'CATASTRO_MASTER_GATEWAY_TOKEN':'x'*48,
                'CATASTRO_MASTER_GATEWAY_FILE':'Z:/not-present/master.env'}
        with patch.dict(os.environ,values):
            self.assertEqual(configuration(),(values['CATASTRO_MASTER_GATEWAY_URL'],values['CATASTRO_MASTER_GATEWAY_TOKEN']))

    def test_gateway_endpoint_is_restricted_to_named_cloudflare_worker(self):
        with patch.dict(os.environ,{'CATASTRO_MASTER_GATEWAY_URL':'https://example.invalid',
                                    'CATASTRO_MASTER_GATEWAY_TOKEN':'x'*48,
                                    'CATASTRO_MASTER_GATEWAY_FILE':'Z:/not-present/master.env'}):
            with self.assertRaisesRegex(StorageError,'Worker privado'):
                configuration()

    def test_production_enable_switch_overrides_local_preview_and_defaults_off(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertFalse(enabled())
        with patch.dict(os.environ,{'CATASTRO_MASTER_ENABLED':'0','CATASTRO_MASTER_LOCAL_PREVIEW':'1'}):
            self.assertFalse(enabled())
        with patch.dict(os.environ,{'CATASTRO_MASTER_ENABLED':'1','CATASTRO_MASTER_LOCAL_PREVIEW':'0'}):
            self.assertTrue(enabled())


class FakeGateway:
    def __init__(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.db.executescript(Path(__file__).with_name('master_schema.sql').read_text(encoding='utf8'))
        self.saved={};self.fail=False
    def revision(self):return int(self.db.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])
    def read(self,sql,params=()):return [dict(r) for r in self.db.execute(sql,params)]
    def call(self,payload):
        if payload['id'] in self.saved:return self.saved[payload['id']]
        if payload['revision']!=self.revision():raise Conflict('stale')
        if self.fail:raise RuntimeError('network unavailable')
        changes={c['table']:c for c in payload['changes']}
        with self.db:
            for table in reversed(TABLES):
                for row in changes.get(table,{}).get('deletes',[]):
                    self.db.execute('DELETE FROM '+table+' WHERE '+' AND '.join(k+'=?' for k in TABLES[table]),row)
            for table in TABLES:
                names=[r[1] for r in self.db.execute('PRAGMA table_info('+table+')')]
                other=[n for n in names if n not in TABLES[table]]
                suffix=' DO UPDATE SET '+','.join(n+'=excluded.'+n for n in other) if other else ' DO NOTHING'
                query='INSERT INTO '+table+' VALUES ('+','.join('?' for _ in names)+') ON CONFLICT ('+','.join(TABLES[table])+')'+suffix
                self.db.executemany(query,changes.get(table,{}).get('upserts',[]))
        result={'result':payload['result']};self.saved[payload['id']]=result;return result


class DurableMasterTests(TestCase):
    def setUp(self):self.gateway=FakeGateway();self.store=D1Store(self.gateway)
    def test_restart_recovers_normalized_rows_and_selection(self):
        self.store.stage(candidate(),0,'admin')
        plan={'revision':1,'mode':'fill','version_id':'v1','scope':{'ubigeo':'040103','kind':'lote'},'reason':'piloto'}
        preview=self.store.preview(plan);self.store.apply(plan,preview['token'],'admin')
        restored=D1Store(self.gateway)
        self.assertEqual(restored.summary()['storage'],'d1')
        self.assertEqual(restored.revision,2)
        self.assertEqual(restored.records(),self.store.records())
        self.assertEqual(restored.collection('040103','lote'),self.store.collection('040103','lote'))
    def test_catalog_review_and_environment_layer_survive_restart(self):
        payload=candidate()
        payload['identifiers']=[{'target_ref':'lote:a','scheme':'referencia_catastral',
                                 'value':'REF-D1','status':'candidate'}]
        payload['environment_features']=[{'kind':'parque','name':'Parque D1',
            'geometry':{'type':'Point','coordinates':[-71.55,-16.36]}}]
        self.store.stage(payload,0,'admin')
        item=self.store.db.execute('SELECT id FROM external_identifiers').fetchone()
        self.store.review_catalog('external_identifiers',item[0],'observed','Cotejo D1',
                                  {'document':'ficha'},1,'admin')
        restored=D1Store(self.gateway)
        self.assertEqual(restored.db.execute(
            'SELECT status FROM catalog_review_status').fetchone()[0],'observed')
        self.assertEqual(len(restored.db.execute('SELECT * FROM catalog_review_events').fetchall()),1)
        self.assertEqual(restored.db.execute(
            'SELECT name FROM environment_features').fetchone()[0],'Parque D1')
    def test_another_process_invalidates_preview(self):
        self.store.stage(candidate(),0,'admin');other=D1Store(self.gateway)
        self.store.stage(candidate(version='v2'),1,'admin')
        with self.assertRaises(Conflict):other.stage(candidate(version='v3'),1,'admin')
        self.assertEqual(self.gateway.revision(),2)
    def test_failed_commit_discards_unconfirmed_cache_on_next_read(self):
        self.gateway.fail=True
        with self.assertRaises(RuntimeError):self.store.stage(candidate(),0,'admin')
        self.gateway.fail=False
        self.assertEqual(self.store.summary()['sources'],[])
        self.assertEqual(self.store.revision,0)
    def test_project_and_restore_persist_as_transactions(self):
        self.store.project('pilot','Piloto','040103',34)
        self.assertEqual(self.store.revision,1)
        self.store.project('pilot','Piloto','040103',34)
        self.assertEqual(self.gateway.revision(),1)
        self.store.stage(candidate(),1,'admin')
        self.store.restore(1,2,'admin','Recuperar selección inicial')
        self.assertEqual(D1Store(self.gateway).revision,3)

    def test_district_edits_share_person_identity_without_overwriting_other_districts(self):
        def unit(ubigeo,source,version,name):
            payload=candidate(source,version,kind='unidad',fields={'bathrooms':2})
            payload['source']['ubigeo']=ubigeo;payload['features'][0]['geometry']=None
            payload['people']=[{'source_record_id':'a','name':name,'document_type':'DNI','document_number':'00000001','row':1}]
            self.store.stage(payload,self.gateway.revision(),'admin')
            plan={'revision':self.gateway.revision(),'mode':'fill','version_id':version,
                  'scope':{'ubigeo':ubigeo,'kind':'unidad'},'reason':'Piloto sintético'}
            self.store.apply(plan,self.store.preview(plan)['token'],'admin')
        unit('040103','cayma','v-cayma','Nombre documentado')
        unit('040126','yanahuara','v-yanahuara','Nombre discordante')
        self.assertEqual(self.store.summary('040126')['sources'][0]['id'],'yanahuara')
        self.assertEqual(len(self.store.summary('040126')['sources']),1)
        self.assertEqual(len(self.store.records({'owner_document_number':'00000001'})),2)
        person=self.gateway.read('SELECT * FROM people')[0]
        self.assertEqual(person['name'],'Nombre documentado')
        self.assertEqual(person['source_version'],'v-cayma')
        self.store.restore(1,4,'admin','Retirar selección de Cayma')
        cayma=self.store.records({'ubigeo':'040103'})[0]
        yanahuara=self.store.records({'ubigeo':'040126'})[0]
        self.assertIsNone(cayma['bathrooms'])
        self.assertEqual(yanahuara['bathrooms'],2)
        self.assertEqual(self.gateway.read('SELECT count(*) total FROM people')[0]['total'],1)

    def test_history_stores_changes_instead_of_repeating_all_selected_values(self):
        self.store.stage(candidate(),0,'admin')
        plan={'revision':1,'mode':'fill','version_id':'v1','scope':{'ubigeo':'040103','kind':'lote'},'reason':'Piloto'}
        self.store.apply(plan,self.store.preview(plan)['token'],'admin')
        restored=D1Store(self.gateway)
        restored.stage(candidate(version='v2'),2,'admin')
        snapshot=json.loads(self.gateway.read('SELECT snapshot_json FROM journal WHERE revision=3')[0]['snapshot_json'])
        self.assertEqual(snapshot['format'],2)
        self.assertEqual(snapshot['selection_changes'],[])
        restored.restore(2,3,'admin','Recuperar revisión previa')
        self.assertEqual(len(restored.collection('040103','lote')['features']),1)
