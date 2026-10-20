import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase
from . import source_placement, shared_placement, master_layers, master_views
from .storage import StorageError, PreconditionFailed


class Cloud:
    def __init__(self):
        self.objects = {}
        self.race = None
        self.fail = False
        self.lose_ack = False

    def get(self, key):
        if key not in self.objects:
            raise StorageError('R2 respondió HTTP 404.', 404)
        data = self.objects[key]
        return data, {'ETag': '"'+hashlib.md5(data).hexdigest()+'"'}

    def put_verified(self, key, data, content_type):
        if self.fail:
            raise StorageError('Sin conexión')
        self.objects[key] = data

    def put_conditional(self, key, data, etag=None):
        if self.race:
            fn, self.race = self.race, None
            fn()
        actual = self.get(key)[1]['ETag'] if key in self.objects else None
        if actual != etag:
            raise PreconditionFailed('Conflicto', 412)
        self.objects[key] = data
        if self.lose_ack:
            self.lose_ack = False
            raise StorageError('Respuesta perdida')


class SharedPlacementTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = 'cayma-pud-2006-eu03'
        self.folder = Path(self.temp.name)/self.source
        self.folder.mkdir()
        ring = [[-71.55,-16.37],[-71.549,-16.37],[-71.549,-16.369],[-71.55,-16.369],[-71.55,-16.37]]
        for name in ('lotes', 'manzanas'):
            f = {'id':'block-a' if name == 'manzanas' else 'lot-a', 'properties':{'BLOCK_REF':'block-a'},
                 'geometry':{'type':'Polygon','coordinates':[ring]}}
            (self.folder/(name+'.geojson')).write_text(json.dumps({'type':'FeatureCollection','features':[f]}),encoding='utf8')
        (self.folder/'metadata.json').write_text(json.dumps({'id':self.source,'ubigeo':'040103','active':True,
            'bbox':[-71.55,-16.37,-71.549,-16.369],'reference_only':True,'crs':'EPSG:4326'}),encoding='utf8')
        self.local = dict(revision=7,east_m=4,north_m=-5,locked=True,
                          blocks={'block-a':dict(east_m=6,north_m=7,scale=1.1)},history=[dict(revision=6)])
        self.original = json.dumps(self.local).encode()
        (self.folder/'placement.json').write_bytes(self.original)
        self.cloud = Cloud()
        for context in (patch.dict('os.environ',{'CATASTRO_SHARED_PLACEMENTS':'1'}),
                        patch('catastro.shared_placement.R2',return_value=self.cloud),
                        patch.dict(master_layers.SOURCES,{self.source:self.folder})):
            context.start();self.addCleanup(context.stop)

    def test_migrate_then_read_and_save_across_instances_without_touching_local_file(self):
        initial = shared_placement.initialize(self.folder)
        self.assertEqual(initial['revision'],7)
        self.assertEqual(initial['blocks'],self.local['blocks'])
        archived = json.loads(self.cloud.objects[initial['history'][0]['object_key']])
        self.assertEqual(archived,self.local)
        payload = {**initial,'blocks':{'block-a':dict(east_m=30,north_m=20,scale=1.5)}}
        saved = source_placement.save(self.folder,payload,'admin')
        self.assertEqual(saved['revision'],8)
        self.assertEqual(source_placement.read(self.folder),saved)
        self.assertEqual((self.folder/'placement.json').read_bytes(),self.original)
        layer = master_layers.layer(self.source,'lotes','040103')
        p = layer['features'][0]['geometry']['coordinates'][0]
        result = master_layers.radius(self.source,(p[0][1]+p[2][1])/2,(p[0][0]+p[2][0])/2,100)
        self.assertEqual(result['lots']['features'],layer['features'])
        self.assertEqual(result['blocks']['placement']['revision'],8)
        self.assertEqual(master_layers.revisions()[self.source],8)
        with self.assertRaises(source_placement.Conflict):
            source_placement.save(self.folder,payload,'other window')
        with self.assertRaises(source_placement.Conflict):
            shared_placement.initialize(self.folder)

    def test_atomic_conflict_cannot_overwrite_another_winner(self):
        current = shared_placement.initialize(self.folder)
        winner = {**current,'revision':8,'east_m':99}
        self.cloud.race = lambda:self.cloud.objects.update({shared_placement.key(self.folder):shared_placement.encoded(winner)})
        with self.assertRaises(source_placement.Conflict):
            source_placement.save(self.folder,current,'loser')
        self.assertEqual(source_placement.read(self.folder),winner)

    def test_storage_failure_does_not_report_saved_or_fall_back_to_uncorrected_geometry(self):
        current = shared_placement.initialize(self.folder)
        self.cloud.fail = True
        with self.assertRaises(StorageError):source_placement.save(self.folder,current,'admin')
        self.assertEqual(source_placement.read(self.folder)['revision'],7)
        del self.cloud.objects[shared_placement.key(self.folder)]
        with self.assertRaises(StorageError):master_layers.layer(self.source,'lotes','040103')
        self.assertEqual((self.folder/'placement.json').read_bytes(),self.original)

    def test_lost_ack_is_verified_without_duplicate_revision(self):
        current = shared_placement.initialize(self.folder)
        self.cloud.lose_ack = True
        saved = source_placement.save(self.folder,current,'admin')
        self.assertEqual(saved['revision'],8)
        self.assertEqual(source_placement.read(self.folder),saved)

    def test_admin_api_preserves_acl_and_returns_503_when_shared_store_is_unavailable(self):
        from django.test import RequestFactory
        from types import SimpleNamespace
        r=RequestFactory().get('/catastro/api/maestro/fuentes/'+self.source+'/posicion/')
        r.current_user=SimpleNamespace(is_authenticated=True,is_active=True,is_staff=False,is_superuser=False)
        self.assertEqual(master_views.placement(r,self.source).status_code,403)
        r.current_user.is_staff=True
        self.assertEqual(master_views.placement(r,self.source).status_code,503)
