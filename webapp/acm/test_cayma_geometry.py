import json
from types import SimpleNamespace
from unittest.mock import patch
from django.test import RequestFactory, SimpleTestCase
from . import cadastral_views
from .access import DEFAULTS
from catastro import master_layers


class CaymaRadiusTests(SimpleTestCase):
    source = 'cayma-pud-2006-eu03'

    def request(self, allowed=True):
        request = RequestFactory().get('/acm/catastro/fuentes/'+self.source+'/radio/',
                                       {'lat': '-16.36', 'lng': '-71.545', 'radius': '500'})
        request.acm_access = SimpleNamespace(permissions={**DEFAULTS, 'cadastral_info': allowed})
        return request

    def test_acm_checks_role_before_reading_reference_geometry(self):
        with patch('catastro.master_layers.radius') as read:
            self.assertEqual(cadastral_views.reference_geometry(self.request(False), self.source).status_code, 403)
            read.assert_not_called()
        self.assertEqual(cadastral_views.reference_geometry(RequestFactory().get('/'), self.source).status_code, 401)

    def test_revision_checks_keep_role_permissions_and_shared_failures_are_explicit(self):
        from catastro.storage import StorageError
        with patch('catastro.master_layers.revisions',return_value={self.source:97}) as read:
            self.assertEqual(cadastral_views.revisions(self.request(False)).status_code,403)
            read.assert_not_called()
            response=cadastral_views.revisions(self.request())
            self.assertEqual(json.loads(response.content),{'sources':{self.source:97}})
            self.assertIn('no-store',response['Cache-Control'])
        with patch('catastro.master_layers.revisions',side_effect=StorageError('No disponible')):
            self.assertEqual(cadastral_views.revisions(self.request()).status_code,503)
        with patch('catastro.master_layers.radius',side_effect=StorageError('No disponible')):
            self.assertEqual(cadastral_views.reference_geometry(self.request(),self.source).status_code,503)

    def test_cayma_reference_radius_is_delivered_through_the_acm_permission(self):
        response = cadastral_views.reference_geometry(self.request(), self.source)
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertGreater(len(result['lots']['features']), 100)
        self.assertGreater(len(result['blocks']['features']), 10)
        self.assertLess(len(result['lots']['features']), 22405)
        self.assertTrue(result['reference_only'])
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_outside_source_radius_is_empty_and_bad_parameters_are_rejected(self):
        self.assertEqual(master_layers.radius(self.source, -12, -77, 500)['lots']['features'], [])
        for args in [(float('nan'), -71.5, 500), (-16.36, -71.545, 5000)]:
            with self.assertRaises(ValueError):master_layers.radius(self.source, *args)
