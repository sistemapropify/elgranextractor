import io
import json
import hashlib
import sqlite3
from unittest.mock import patch
from django.test import SimpleTestCase
from catastro.state import State
from catastro.external_worker import seed_memory_index
from catastro.test_collector import FakeSource,FakeR2,LOT
from scrapi.geollaqta_scraper import collect


class MemoryCollectorTests(SimpleTestCase):
    def test_documents_and_index_never_create_disk_files(self):
        real_connect=sqlite3.connect
        def connect(database,*args,**kwargs):
            self.assertEqual(database,':memory:')
            return real_connect(database,*args,**kwargs)
        with patch('catastro.state.sqlite3.connect',side_effect=connect),patch('pathlib.Path.mkdir',side_effect=AssertionError('disk directory')),patch('pathlib.Path.open',side_effect=AssertionError('disk file')):
            state=State(memory=True)
            source,cloud=FakeSource(),FakeR2();source.missing=False
            result=collect('040117',lot_id=LOT,state=state,source=source,r2=cloud,keep_local=False,workers=2)
            self.assertEqual((result['processed'],result['uploaded']),(1,1))
            self.assertEqual(state.lot(LOT)['uploaded'],1)
            self.assertEqual(state.db.execute('PRAGMA database_list').fetchone()[2],'')
            self.assertEqual(state.db.execute('PRAGMA temp_store').fetchone()[0],2)
            self.assertEqual(list(state.root.rglob('*')),[])
            manifest=json.loads(cloud.objects['geollaqta/040117/'+LOT+'/datos.json'][0])
            self.assertTrue(manifest['artifacts'])
            before=len(source.gets)
            again=collect('040117',lot_id=LOT,state=state,source=source,r2=cloud,keep_local=False)
            self.assertEqual(again['processed'],0);self.assertEqual(len(source.gets),before)
            state.close()

    def test_verified_remote_index_is_loaded_without_a_sqlite_file(self):
        old=State(memory=True)
        old.save_lot(LOT,'040117',object_id=1,status='complete',uploaded=1)
        body=old.db.serialize();old.close()
        key='geollaqta/_ledger/local-retired-20261019-'+hashlib.sha256(body).hexdigest()+'.sqlite3'
        cloud=FakeR2();cloud.objects[key]=(body,'application/vnd.sqlite3')
        state=State(memory=True)
        with patch('pathlib.Path.open',side_effect=AssertionError('disk file')):
            seed_memory_index(state,cloud,key)
        self.assertEqual(state.lot(LOT)['uploaded'],1)
        with self.assertRaises(ValueError):seed_memory_index(state,cloud,key.replace('20261019','invalid'))
        state.close()
