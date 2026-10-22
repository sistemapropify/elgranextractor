import hashlib,json
from unittest import TestCase
from .master_store import MasterStore
from .master_ingest import prepare
from .master_indexing import stage_archived_lot
from .storage import StorageError


class FutureIndexingTests(TestCase):
    def setUp(self):
        self.manifest={'schema_version':1,'extraction_revision':3,'lot_id':'04010300000001',
                       'district_ubigeo':'040103','feature':{'attributes':{},'geometry':{}},'artifacts':[],
                       'reports':[],'missing':[]}
        self.store=MasterStore();self.addCleanup(self.store.db.close)
    def cloud(self,manifest):
        body=json.dumps(manifest).encode()
        class Cloud:
            def get(self,key):
                if key.endswith('/datos.json') or key.endswith('datos-'+hashlib.sha256(body).hexdigest()+'.json'):return body,{}
                raise AssertionError('Se pidió un archivo ajeno al nuevo archivo confirmado.')
        return Cloud()
    def test_missing_immutable_snapshot_is_rebuilt_from_hashed_manifest(self):
        body=json.dumps(self.manifest).encode()
        digest=hashlib.sha256(body).hexdigest()
        class Cloud:
            repaired=None
            def get(self,key):
                if key.endswith('/datos.json'):return body,{}
                if key.endswith('datos-'+digest+'.json'):raise StorageError('missing',404)
                raise AssertionError('Se pidió un archivo ajeno al nuevo archivo confirmado.')
            def put_verified(self,key,data,mime):
                self.repaired=(key,data,mime)
        cloud=Cloud()
        stage_archived_lot('040103',self.manifest['lot_id'],self.store,cloud)
        self.assertEqual(cloud.repaired[1],body)
        self.assertTrue(cloud.repaired[0].endswith('datos-'+digest+'.json'))
        self.assertEqual(cloud.repaired[2],'application/json')
    def test_roundtrip_embedded_candidate_does_not_change_identity(self):
        before=prepare(self.manifest)
        self.manifest['master_candidate']=before
        self.assertEqual(prepare(self.manifest),before)
    def test_new_snapshot_is_staged_once_without_activating_geometry(self):
        result=stage_archived_lot('040103',self.manifest['lot_id'],self.store,self.cloud(self.manifest))
        repeated=stage_archived_lot('040103',self.manifest['lot_id'],self.store,self.cloud(self.manifest))
        self.assertTrue(repeated['unchanged']);self.assertEqual(self.store.revision,1)
        self.assertEqual(self.store.records(),[])
        payload=json.loads(self.store.db.execute('SELECT payload FROM versions').fetchone()[0])
        self.assertIn('/datos-',payload['version']['original']['object_key'])
        self.assertEqual(payload['version']['original']['archive_status'],'verified_r2')
    def test_historical_revision_cannot_enter_via_future_indexing(self):
        self.manifest['extraction_revision']=2
        with self.assertRaisesRegex(ValueError,'históricas'):
            stage_archived_lot('040103',self.manifest['lot_id'],self.store,self.cloud(self.manifest))
        self.assertEqual(self.store.revision,0)
