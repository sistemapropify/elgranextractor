from io import BytesIO
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase
from PIL import Image

from . import master_views, raster_overlays
from .master_store import MasterStore


class FakeCloud:
    def __init__(self):
        self.values = {}

    def put_verified(self, key, body, content_type):
        self.values[key] = body

    def get(self, key):
        return self.values[key], {}


def image_bytes():
    stream = BytesIO()
    Image.new('RGB', (800, 450), (51, 112, 83)).save(stream, 'JPEG')
    return stream.getvalue()


class RasterOverlayTests(SimpleTestCase):
    def setUp(self):
        self.store = MasterStore()
        self.addCleanup(self.store.db.close)
        self.cloud = FakeCloud()

    def test_drone_image_is_a_versioned_master_layer_with_adjustable_footprint(self):
        body = image_bytes()
        overlay = raster_overlays.register_image(
            self.store, body, 'foto -16.385470 -71.547682.jpg',
            'Dron Yanahuara', '040126', cloud=self.cloud)
        self.assertTrue(overlay['id'].startswith(raster_overlays.SOURCE_PREFIX))
        self.assertEqual(overlay['metadata']['center'],
                         {'lat': -16.38547, 'lng': -71.547682})
        self.assertAlmostEqual(overlay['state']['height_m'],
                               overlay['state']['width_m'] * 450 / 800, places=2)
        self.assertEqual(overlay['footprint']['type'], 'Polygon')
        self.assertEqual(len(raster_overlays.list_overlays(self.store, '040126')), 1)
        self.assertEqual(raster_overlays.list_all_overlays(self.store), [])
        self.assertEqual(raster_overlays.image_body(
            self.store, overlay['id'], '040126', cloud=self.cloud)[0], body)

        first_version = overlay['version_id']
        adjusted = raster_overlays.calibrate(
            self.store, overlay['id'], {
                **overlay['state'],
                'width_m': 180,
                'height_m': 101.25,
                'rotation_deg': -4.6,
                'opacity': 0.65,
                'locked': True,
            }, '040126', actor='reviewer')
        self.assertNotEqual(adjusted['version_id'], first_version)
        self.assertEqual(adjusted['state']['width_m'], 180)
        self.assertEqual(adjusted['state']['rotation_deg'], 355.4)
        self.assertTrue(adjusted['state']['locked'])
        current = raster_overlays.list_overlays(self.store, '040126')
        self.assertEqual(current[0]['version_id'], adjusted['version_id'])
        self.assertEqual(len(raster_overlays.list_all_overlays(self.store)), 1)

    def test_image_without_center_is_rejected_before_any_write(self):
        with self.assertRaisesRegex(ValueError, 'GPS'):
            raster_overlays.register_image(
                self.store, image_bytes(), 'foto.jpg', 'Dron', '040126',
                cloud=self.cloud)
        self.assertEqual(self.store.revision, 0)

    @patch('catastro.master_views.source_manager.store')
    @patch('catastro.master_views.source_manager.durable', return_value=True)
    @patch('catastro.master_views.source_manager.enabled', return_value=False)
    def test_durable_azure_storage_serves_the_master_raster(
            self, enabled, durable, store):
        store.return_value = self.store
        self.assertIs(master_views._raster_store(), self.store)

    @patch('catastro.master_views.source_manager.durable', return_value=False)
    @patch('catastro.master_views.source_manager.enabled', return_value=False)
    def test_raster_is_unavailable_without_local_or_durable_storage(
            self, enabled, durable):
        with self.assertRaisesRegex(PermissionError, 'no está habilitado'):
            master_views._raster_store()

    def test_private_upload_and_calibration_routes_store_master_versions(self):
        factory = RequestFactory()
        actor = SimpleNamespace(is_authenticated=True, is_active=True, is_staff=True,
                                is_superuser=False, username='reviewer')
        upload = SimpleUploadedFile(
            'foto -16.385470 -71.547682.jpg', image_bytes(), content_type='image/jpeg')
        request = factory.post('/catastro/api/maestro/raster/', {
            'name': 'Parche Yanahuara', 'ubigeo': '040126', 'image': upload})
        request.current_user = actor
        request._dont_enforce_csrf_checks = True
        with patch('catastro.master_views._raster_store', return_value=self.store):
            response = master_views.raster_layers(request)
        self.assertEqual(response.status_code, 200, response.content)
        overlay = json.loads(response.content)['overlay']

        state = {**overlay['state'], 'width_m': 175, 'height_m': 98.44,
                 'opacity': 1, 'locked': True}
        request = factory.post(
            '/catastro/api/maestro/raster/' + overlay['id'] + '/calibracion/',
            data=json.dumps({'ubigeo': '040126', 'state': state}),
            content_type='application/json')
        request.current_user = actor
        request._dont_enforce_csrf_checks = True
        with patch('catastro.master_views._raster_store', return_value=self.store):
            response = master_views.raster_calibration(request, overlay['id'])
        self.assertEqual(response.status_code, 200, response.content)
        adjusted = json.loads(response.content)['overlay']
        self.assertEqual(adjusted['state']['width_m'], 175)
        self.assertTrue(adjusted['state']['locked'])

        request = factory.get('/catastro/api/maestro/raster/catalogo/')
        request.current_user = actor
        with patch('catastro.master_views._raster_store', return_value=self.store):
            response = master_views.raster_catalog(request)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(json.loads(response.content)['overlays'][0]['id'], overlay['id'])
