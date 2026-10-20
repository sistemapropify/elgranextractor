import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase
from django.test import RequestFactory
from types import SimpleNamespace
from . import source_placement, master_layers


class SourcePlacementTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = 'cayma-pud-2006-eu03'
        meta = {'id': self.source, 'ubigeo': '040103', 'active': True, 'bbox': [-71.55,-16.37,-71.54,-16.36],
                'reference_only': True, 'crs': 'EPSG:4326'}
        (self.folder/'metadata.json').write_text(json.dumps(meta), encoding='utf8')
        polygon = {'type': 'Polygon', 'coordinates': [[[-71.55,-16.37],[-71.54,-16.37],[-71.54,-16.36],[-71.55,-16.36],[-71.55,-16.37]]]}
        for key in ('lotes', 'manzanas'):
            (self.folder/(key+'.geojson')).write_text(json.dumps({'type': 'FeatureCollection', 'features': [
                {'id': key+'-stable', 'properties': {'ID_LOTE': None}, 'geometry': polygon}]}), encoding='utf8')
        fixture = patch.dict(master_layers.SOURCES, {self.source: self.folder})
        fixture.start()
        self.addCleanup(fixture.stop)

    def test_frozen_translation_moves_both_layers_and_preserves_source_bytes_and_ids(self):
        originals = {key: (self.folder/(key+'.geojson')).read_bytes() for key in ('lotes','manzanas')}
        before = master_layers.layer(self.source, 'lotes', '040103')['features'][0]
        value = source_placement.save(self.folder, dict(revision=0,east_m=15,north_m=-10,locked=True), 'test')
        self.assertTrue(value['locked'])
        self.assertEqual(value['revision'], 1)
        for key in ('lotes','manzanas'):
            moved = master_layers.layer(self.source, key, '040103')['features'][0]
            self.assertEqual(moved['id'], key+'-stable')
            self.assertGreater(moved['geometry']['coordinates'][0][0][0], before['geometry']['coordinates'][0][0][0])
            self.assertLess(moved['geometry']['coordinates'][0][0][1], before['geometry']['coordinates'][0][0][1])
            self.assertEqual((self.folder/(key+'.geojson')).read_bytes(), originals[key])
        self.assertNotIn('updated_by', master_layers.source_metadata(self.source)['placement'])

    def test_stale_window_cannot_overwrite_a_saved_registration(self):
        payload = dict(revision=0,east_m=10,north_m=20,locked=True)
        source_placement.save(self.folder, payload, 'test')
        with self.assertRaises(source_placement.Conflict):
            source_placement.save(self.folder, payload, 'other')
        second = source_placement.save(self.folder, {**payload,'revision':1,'east_m':0,'north_m':0}, 'test')
        self.assertEqual(second['revision'], 2)
        self.assertEqual(second['history'][-1]['east_m'], 10)

    def test_unlocked_and_non_finite_or_excessive_offsets_cannot_be_saved(self):
        for payload in [dict(revision=0,east_m=0,north_m=0,locked=False),
                        dict(revision=0,east_m=float('nan'),north_m=0,locked=True),
                        dict(revision=0,east_m=2001,north_m=0,locked=True)]:
            with self.assertRaises(ValueError):source_placement.save(self.folder,payload,'test')
        self.assertFalse((self.folder/'placement.json').exists())

    def test_only_admin_can_freeze_a_source_and_stale_revision_is_http_409(self):
        from .master_views import placement
        factory = RequestFactory()
        def request(staff, revision):
            value = factory.post('/catastro/api/maestro/fuentes/'+self.source+'/posicion/',
                                 json.dumps(dict(revision=revision,east_m=5,north_m=-5,locked=True)),
                                 content_type='application/json')
            value._dont_enforce_csrf_checks = True
            value.current_user = SimpleNamespace(is_authenticated=True,is_active=True,is_staff=staff,is_superuser=False,username='test')
            return value
        self.assertEqual(placement(request(False,0),self.source).status_code,403)
        self.assertFalse((self.folder/'placement.json').exists())
        self.assertEqual(placement(request(True,0),self.source).status_code,200)
        self.assertEqual(placement(request(True,0),self.source).status_code,409)

    def test_cuadrantizacion_can_read_reference_without_administrative_write_permission(self):
        from cuadrantizacion.reference_views import layer
        request = RequestFactory().get('/cuadrantizacion/referencias/'+self.source+'/lotes/?ubigeo=040103')
        self.assertEqual(layer(request,self.source,'lotes').status_code,401)
        request.current_user = SimpleNamespace(is_authenticated=True,is_active=True,is_staff=False,is_superuser=False)
        self.assertEqual(layer(request,self.source,'lotes').status_code,200)

    def test_local_collector_redirect_does_not_intercept_master_position_requests(self):
        import os
        from .master_views import placement
        from .views import admin_required
        from django.http import HttpResponse
        factory = RequestFactory()
        user = SimpleNamespace(is_authenticated=True,is_active=True,is_staff=True,is_superuser=False,username='test')
        path = '/catastro/api/maestro/fuentes/'+self.source+'/posicion/'
        request = factory.get(path)
        request.current_user = user
        with patch.dict(os.environ, {'CATASTRO_DISABLE_LOCAL_COLLECTION': '1'}):
            response = placement(request, self.source)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.content)['revision'], 0)
            self.assertNotIn('Location', response)
            for path in ('/catastro/maestro/', '/catastro/visor-planos/', '/catastro/api/planos/test/'):
                request = factory.get(path)
                request.current_user = user
                self.assertEqual(admin_required(lambda r: HttpResponse('local'))(request).status_code, 200)
            request = factory.get('/catastro/api/status/')
            request.current_user = user
            response = admin_required(lambda r: HttpResponse('collector'))(request)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response['Location'], 'https://acm.propifai.com/catastro/api/status/')
