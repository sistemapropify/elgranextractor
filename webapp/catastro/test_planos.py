from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from .planos_views import viewer


class PlanViewerTests(SimpleTestCase):
    def setUp(self):
        template_patch = patch('django.template.base.Template._render',
                               lambda template, context: template.nodelist.render(context))
        template_patch.start()
        self.addCleanup(template_patch.stop)

    def request(self, **permissions):
        request = RequestFactory().get('/catastro/visor-planos/')
        request.current_user = SimpleNamespace(is_authenticated=True, is_active=True,
                                               is_staff=False, is_superuser=False, **permissions)
        return request

    def test_anonymous_cannot_open_plan_workspace(self):
        request = RequestFactory().get('/catastro/visor-planos/')
        response = viewer(request)
        self.assertEqual(response.status_code, 302)

    def test_regular_account_cannot_open_administrative_plan_workspace(self):
        self.assertEqual(viewer(self.request()).status_code, 403)

    @override_settings(GOOGLE_MAPS_API_KEY='maps-test-key')
    def test_staff_gets_map_workspace_and_collapsible_cards(self):
        request = self.request()
        request.current_user.is_staff = True
        response = viewer(request)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Visor de planos', html)
        self.assertIn('id="planos-map"', html)
        self.assertEqual(html.count('<details class="planos-card"'), 5)
        self.assertIn('Abrir archivo DWG', html)
        self.assertIn('accept=".dwg,', html)
        self.assertNotIn('Abrir archivo GeoJSON', html)
        self.assertIn('visor-planos.js?v=4', html)
        self.assertIn('maps-test-key', html)
        self.assertIn('visor-planos/', html)
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    @override_settings(GOOGLE_MAPS_API_KEY='')
    def test_no_key_has_an_explicit_configuration_message(self):
        request = self.request()
        request.current_user.is_superuser = True
        html = viewer(request).content.decode()
        self.assertIn('Google Maps está pendiente de configuración', html)
        self.assertNotIn('maps.googleapis.com/maps/api/js', html)
