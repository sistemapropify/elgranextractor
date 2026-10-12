import json
from unittest.mock import patch

from django.http import Http404
from django.test import TestCase, RequestFactory
from django.urls import reverse

from intelligence.models import Role, User
from .components_engine import parameters, candidates, calculate
from .components_history import persist_component_history, replication_parameters
from .components_views import replicate_history
from .models import ACMLink
from .test_components import params, sample
from .views import historial_acm


class HistoryReplicationTests(TestCase):
    def setUp(self):
        role = Role.objects.create(name='agent')
        self.user = User.objects.create(username='replay-owner', phone='900000003', role=role)
        self.other = User.objects.create(username='replay-other', phone='900000004', role=role)
        self.factory = RequestFactory()
        self.p = parameters({**params(), 'property_type': 'Casa', 'radius': 300,
                             'rooms': 0, 'baths': 2.5, 'address': 'Ubicación guardada'})
        rows = candidates(sample(), self.p)
        result = calculate(rows, self.p)
        self.p['manual_valuation'] = 111111
        self.p['report_ids'] = ['a']
        self.p['reference_ids'] = ['b']
        self.p['weight_reference'] = {'land': 999, 'built': 999, 'radius': 999}
        self.history, _ = persist_component_history(self.user, self.p, rows, result)

    def request(self, owner=None, method='get'):
        request = getattr(self.factory, method)(reverse('acm:componentes_historial_replicar', args=[self.history.pk]))
        request.current_user = owner or self.user
        return request

    @patch('cuadrantizacion.map_layers.map_layers_config', return_value={'raster': [], 'vectoriales': [], 'zonas': []})
    def test_prefill_uses_saved_target_without_mutating_or_saving_history(self, layers):
        original = dict(self.history.parametros_json)
        with patch('acm.components_views.render', wraps=__import__('django.shortcuts', fromlist=['render']).render) as render:
            response = replicate_history(self.request(), self.history.pk)
        saved = render.call_args.args[2]['replication']['params']
        for key in ('lat', 'lng', 'land', 'built', 'property_type', 'radius', 'max_radius', 'rooms', 'baths', 'sources', 'address'):
            self.assertEqual(saved[key], self.p[key])
        for key in ('manual_valuation', 'reference_ids', 'report_ids', 'weight_reference', 'excluded_ids'):
            self.assertNotIn(key, saved)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertContains(response, 'Buscar y calcular')
        self.assertContains(response, 'cmp-replication-data')
        self.history.refresh_from_db()
        self.assertEqual(self.history.parametros_json, original)
        self.assertEqual(ACMLink.objects.count(), 1)

    def test_other_agent_cannot_load_coordinates(self):
        with self.assertRaises(Http404):
            replicate_history(self.request(self.other), self.history.pk)

    def test_logged_out_or_inactive_user_rejected(self):
        anonymous = self.factory.get('/replicate/')
        self.assertEqual(replicate_history(anonymous, self.history.pk).status_code, 401)
        self.user.is_active = False
        self.assertEqual(replicate_history(self.request(), self.history.pk).status_code, 401)

    def test_get_only(self):
        self.assertEqual(replicate_history(self.request(method='post'), self.history.pk).status_code, 405)

    def test_legacy_record_without_target_coordinates_is_not_guessed(self):
        self.history.parametros_json.pop('lat')
        self.history.save(update_fields=['parametros_json'])
        self.assertIsNone(replication_parameters(self.history))
        self.assertEqual(replicate_history(self.request(), self.history.pk).status_code, 409)
        self.history.metodo = 'clasico'
        self.history.parametros_json = self.p
        self.assertIsNone(replication_parameters(self.history))

    def test_invalid_non_finite_coordinates_cannot_be_replicated(self):
        for value in ('nan', 'inf', 100):
            self.history.parametros_json = {**self.p, 'lat': value}
            self.assertIsNone(replication_parameters(self.history))

    def test_all_supported_types_restore_valid_areas_and_optional_zero(self):
        for kind in ('Casa', 'Terreno', 'Departamento', 'Oficina'):
            self.history.parametros_json = {**params(), 'property_type': kind, 'rooms': 0, 'baths': 0, 'floor': 0}
            saved = replication_parameters(self.history)
            self.assertEqual(saved['property_type'], kind)
            self.assertEqual(saved['lat'], params()['lat'])
            self.assertEqual(saved['baths'], None if kind == 'Terreno' else 0)

    def test_history_button_uses_owner_scoped_uuid(self):
        response = historial_acm(self.request())
        url = reverse('acm:componentes_historial_replicar', args=[self.history.pk])
        self.assertContains(response, 'Replicar ACM')
        self.assertContains(response, url)

    @patch('cuadrantizacion.map_layers.map_layers_config', return_value={'raster': [], 'vectoriales': [], 'zonas': []})
    def test_address_is_inert_json_and_not_a_script(self, layers):
        attack = '</script><script>alert(1)</script>'
        self.history.parametros_json['address'] = attack
        self.history.save(update_fields=['parametros_json'])
        response = replicate_history(self.request(), self.history.pk)
        self.assertNotContains(response, attack)
        self.assertContains(response, '\\u003C/script\\u003E')
