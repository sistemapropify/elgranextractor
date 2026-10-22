from types import SimpleNamespace
from copy import deepcopy
from unittest.mock import patch
from django.conf import settings

from django.test import RequestFactory, SimpleTestCase, override_settings

from .planos_views import viewer


class PlanViewerTests(SimpleTestCase):
    def setUp(self):
        templates = deepcopy(settings.TEMPLATES)
        templates[0]['APP_DIRS'] = False
        templates[0]['OPTIONS']['context_processors'] = ['django.template.context_processors.request']
        templates[0]['OPTIONS']['loaders'] = [
            ('django.template.loaders.locmem.Loader', {'propifai_base.html': '<html><head>{% block extra_head %}{% endblock %}</head><body>{% block content %}{% endblock %}{% block extra_js %}{% endblock %}</body></html>'}),
            'django.template.loaders.filesystem.Loader', 'django.template.loaders.app_directories.Loader']
        template_settings = override_settings(TEMPLATES=templates)
        template_settings.enable()
        self.addCleanup(template_settings.disable)
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

    def test_completed_import_is_bootstrapped_without_a_second_status_request(self):
        request=self.request()
        request.current_user.is_staff=True
        request.GET=request.GET.copy()
        request.GET['plano']='a'*32
        with patch('catastro.cad_reader.status',return_value={'id':'a'*32,'status':'completed','layers':[]}) as status:
            html=viewer(request).content.decode()
        status.assert_called_once_with('a'*32)
        self.assertIn('id="planos-initial-state"',html)
        self.assertIn('"status": "completed"',html)

    def test_anonymous_cannot_read_bootstrapped_plan_metadata(self):
        request=RequestFactory().get('/catastro/visor-planos/?plano='+'a'*32)
        with patch('catastro.cad_reader.status') as status:
            self.assertEqual(viewer(request).status_code,302)
        status.assert_not_called()

    def test_unknown_plan_does_not_break_workspace(self):
        request=self.request()
        request.current_user.is_staff=True
        request.GET=request.GET.copy()
        request.GET['plano']='invalid'
        with patch('catastro.cad_reader.status',side_effect=ValueError('Plano no encontrado.')):
            self.assertEqual(viewer(request).status_code,200)

    @override_settings(GOOGLE_MAPS_API_KEY='maps-test-key')
    def test_staff_gets_map_workspace_and_collapsible_cards(self):
        request = self.request()
        request.current_user.is_staff = True
        response = viewer(request)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Visor de planos', html)
        self.assertIn('id="planos-map"', html)
        self.assertEqual(html.count('<details class="planos-card"'), 6)
        self.assertIn('Abrir archivo DWG', html)
        self.assertIn('accept=".dwg,', html)
        self.assertNotIn('Abrir archivo GeoJSON', html)
        self.assertIn('visor-planos.js?v=14', html)
        self.assertIn('Mover manzana', html)
        self.assertIn('Mover puntas', html)
        self.assertNotIn('Girar', html)
        self.assertIn('maps-test-key', html)
        self.assertIn('id="planos-edit-card"', html)
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    @override_settings(GOOGLE_MAPS_API_KEY='')
    def test_no_key_has_an_explicit_configuration_message(self):
        request = self.request()
        request.current_user.is_superuser = True
        html = viewer(request).content.decode()
        self.assertIn('Google Maps está pendiente de configuración', html)
        self.assertNotIn('maps.googleapis.com/maps/api/js', html)

    def test_plan_dashboard_explains_the_complete_source_pipeline(self):
        from . import source_manager_views
        request=RequestFactory().get('/catastro/maestro/planos/')
        request.current_user=self.request().current_user
        request.current_user.is_staff=True
        with patch('catastro.source_manager.enabled',return_value=True), \
             patch('catastro.source_manager.durable',return_value=True), \
             patch('catastro.cad_reader.available',return_value=False):
            response=source_manager_views.plans_dashboard(request)
        html=response.content.decode()
        self.assertEqual(response.status_code,200)
        self.assertIn('Ruta del archivo al Catastro Maestro',html)
        self.assertIn('Registrar un original no significa vectorizarlo',html)
        self.assertIn('Aportes parciales por capa y campo',html)
        self.assertIn('catastro-planos-dashboard.js?v=4',html)
        self.assertIn('catastro-planos-dashboard.css?v=4',html)
