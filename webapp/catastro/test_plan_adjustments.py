import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory
from . import cad_reader, plan_adjustments as edits
from .planos_views import adjustments


class PlanAdjustmentTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch('catastro.cad_reader.imports_root', return_value=Path(self.temp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.job = 'c'*32
        self.folder = cad_reader.directory(self.job)
        self.folder.mkdir()
        cad_reader.write_status(self.folder, id=self.job, status='completed')
        self.original = self.folder/'original.dwg'
        self.original.write_bytes(b'original immutable drawing')
        self.ring = [[-71.53,-16.4],[-71.529,-16.4],[-71.529,-16.399],[-71.53,-16.399]]
        self.database = self.folder/'geometries.sqlite3'
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE features(id INTEGER PRIMARY KEY,layer TEXT,geometry TEXT,properties TEXT)')
            for i, layer, geometry in [(1,'MANZANAS',{'type':'Polygon','coordinates':[self.ring+[self.ring[0]]]}),(2,'NUMEROS_LOTES',{'type':'Point','coordinates':[-71.5295,-16.3995]}),(3,'NUMEROS_LOTES',{'type':'Point','coordinates':[-70,-15]})]:
                db.execute('INSERT INTO features VALUES(?,?,?,?)',(i,layer,json.dumps(geometry),'{}'))
        self.original_database = self.database.read_bytes()

    def payload(self, revision=0):
        return dict(revision=revision,groups=[dict(block_id=1,source=self.ring,target=[[x+.0001,y+.0002] for x,y in self.ring],member_ids=[1,2])])

    def test_roundtrip_restore_history_and_original_files_unchanged(self):
        self.assertEqual(edits.read(self.job,'EPSG:4326'),{'revision':0,'groups':[]})
        result=edits.save(self.job,'EPSG:4326',self.payload(),'admin')
        self.assertEqual(result['revision'],1)
        self.assertEqual(edits.read(self.job,'EPSG:4326'),result)
        restored=edits.save(self.job,'EPSG:4326',dict(revision=1,groups=[]),'admin')
        self.assertEqual(restored['groups'],[])
        self.assertEqual(len(list((self.folder/'historial-ajustes').glob('*.json'))),1)
        self.assertEqual(self.original.read_bytes(),b'original immutable drawing')
        self.assertEqual(self.database.read_bytes(),self.original_database)

    def test_stale_revision_does_not_overwrite_another_session(self):
        before=edits.save(self.job,'EPSG:4326',self.payload(),'first')
        with self.assertRaises(edits.Conflict):edits.save(self.job,'EPSG:4326',self.payload(),'second')
        self.assertEqual(edits.read(self.job,'EPSG:4326'),before)

    def test_reject_folded_contour(self):
        value=self.payload()
        value['groups'][0]['target'][1]=[-71.531,-16.398]
        with self.assertRaises(ValueError):edits.save(self.job,'EPSG:4326',value,'admin')
        self.assertEqual(edits.read(self.job,'EPSG:4326')['revision'],0)

    def test_reject_other_lot_and_duplicate_memberships(self):
        value=self.payload();value['groups'][0]['member_ids'].append(3)
        with self.assertRaisesRegex(ValueError,'cruza'):edits.save(self.job,'EPSG:4326',value,'admin')
        value=self.payload();value['groups'].append(value['groups'][0])
        with self.assertRaises(ValueError):edits.save(self.job,'EPSG:4326',value,'admin')

    def test_source_crs_required_and_sources_cannot_be_replaced(self):
        with self.assertRaises(ValueError):edits.read(self.job,'unknown')
        value=self.payload();value['groups'][0]['source']=[[x+.01,y] for x,y in self.ring]
        with self.assertRaisesRegex(ValueError,'original'):edits.save(self.job,'EPSG:4326',value,'admin')

    def request(self, method='get', staff=True):
        factory=RequestFactory()
        request=getattr(factory,method)('/catastro/api/planos/'+self.job+'/ajustes/?crs=EPSG:4326',data=json.dumps(self.payload()) if method=='post' else None,content_type='application/json')
        request.current_user=SimpleNamespace(is_authenticated=True,is_active=True,is_staff=staff,is_superuser=False,username='reviewer')
        return request

    def test_admin_only_and_csrf_required(self):
        self.assertEqual(adjustments(self.request(staff=False),self.job).status_code,403)
        self.assertEqual(adjustments(self.request('post'),self.job).status_code,403)
        anon=RequestFactory().get('/catastro/api/planos/'+self.job+'/ajustes/')
        self.assertEqual(adjustments(anon,self.job).status_code,401)

    def test_endpoint_read_save_and_conflict(self):
        request=self.request('post');request._dont_enforce_csrf_checks=True
        self.assertEqual(adjustments(request,self.job).status_code,200)
        self.assertEqual(adjustments(request,self.job).status_code,409)
        response=adjustments(self.request(),self.job)
        self.assertEqual(json.loads(response.content)['revision'],1)
        self.assertEqual(response['Cache-Control'],'private, no-store')
