import copy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import RequestFactory, TestCase

from .access import (ACMAccess, ACMIdentity, DEFAULTS, get_access, policy_for, required, set_perspective)
from .access_data import issue_snapshot, read_snapshot, opaque_id, persist_history, photo_digest, project
from .access_models import ACMPhotoReview, ACMPortalAnalysis, ACMRoleAudit, ACMRolePolicy
from . import components_views, portal_views
from .components_engine import calculate, candidates, parameters
from .test_components import params, sample


ROLES = [dict(id=18, name='Administrador', area='Administracion', area_id=7, internal=True),
         dict(id=7, name='Desarrollador', area='Tecnologias de la Informacion', area_id=5, internal=True),
         dict(id=8, name='Gerente General', area='Gerencia', area_id=1, internal=True),
         dict(id=20, name='Agente No Afiliado', area='Agentes Inmobiliarios', area_id=8, internal=False),
         dict(id=22, name='Desarrollador de Proyectos', area='Clientes', area_id=9, internal=False)]


class AccessTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.p = parameters(params())
        self.rows = candidates(sample(), self.p)
        self.rows[0].update(source='remax', id='remax-123', code='REMAX-999',
                            title='Remax vende casa', description='https://remax.pe/casa',
                            url='https://remax.pe/casa', first_seen='2026-01-01', last_seen='2026-02-01',
                            first_missing='2026-03-01', record_id=123, image='https://remax.pe/foto.jpg')
        self.result = calculate(self.rows, self.p)
        self.state = dict(params=self.p, records=self.rows, warnings=['Propify no respondió.'])

    def access(self, role=20, owner='77', own=None):
        selected = next(r for r in ROLES if r['id'] == role)
        own_role = next(r for r in ROLES if r['id'] == (own or role))
        permissions, revision = policy_for(selected)
        return ACMAccess(ACMIdentity(owner, 'test-user'), own_role, selected, permissions, revision, '')

    def request(self, path='/acm/analisis/', method='get', data=None, access=None):
        if method == 'post':
            request = self.factory.post(path, data=json.dumps(data or {}), content_type='application/json')
        else:
            request = self.factory.get(path)
        request.session = {}
        request.acm_access = access or self.access()
        request.acm_identity = request.acm_access.user
        request._dont_enforce_csrf_checks = True
        return request

    def test_basic_projection_never_exposes_origin_or_tracking(self):
        state, result, _ = project(self.request(), self.state, self.result)
        raw = json.dumps([state['records'], state['warnings'], result]).lower()
        for forbidden in ('remax', 'properati', 'propify', 'first_seen', 'last_seen', 'first_missing', 'record_id', 'remax.pe', 'state"'):
            self.assertNotIn(forbidden, raw)
        self.assertTrue(state['records'][0]['id'].startswith('c-'))
        for key in ('land', 'built', 'price', 'rooms', 'baths'):
            self.assertEqual(state['records'][0].get(key), self.rows[0].get(key))

    def test_basic_photograph_visible_without_origin_permission(self):
        safe, _, _ = project(self.request(), self.state)
        self.assertTrue(safe['records'][0]['image'].startswith('/acm/fotos/'))
        self.assertTrue(safe['records'][0]['gallery_url'].startswith('/acm/galeria/'))
        self.assertNotIn('remax', safe['records'][0]['image'])

    def test_explicit_review_only_policy_is_respected(self):
        ACMRolePolicy.objects.create(role_id=20, permissions={'unreviewed_photos': False}, updated_by='1')
        safe, _, _ = project(self.request(), self.state)
        self.assertEqual(safe['records'][0]['image'], '')
        ACMPhotoReview.objects.create(digest=photo_digest(self.rows[0]['image']), approved=True, reviewed_by='1')
        safe, _, _ = project(self.request(), self.state)
        self.assertTrue(safe['records'][0]['image'].startswith('/acm/fotos/'))
        self.assertNotIn('remax', safe['records'][0]['image'])

    def test_snapshot_is_confidential_and_cannot_be_used_as_old_signed_payload(self):
        request = self.request()
        token = issue_snapshot(request, self.state)
        self.assertNotIn('remax', token)
        with self.assertRaises(signing.BadSignature):
            signing.loads(token, salt=components_views.SALT)
        self.assertEqual(read_snapshot(request, token), self.state)

    def test_snapshot_rejects_another_owner_role_or_permission_revision(self):
        token = issue_snapshot(self.request(), self.state)
        for access in (self.access(owner='88'), self.access(role=18), self.access()):
            if access.role['id'] == 20 and access.user.pk == '77':
                access.revision = 9
            with self.assertRaises(signing.BadSignature):
                read_snapshot(self.request(access=access), token)

    def test_tampered_token_rejected(self):
        token = issue_snapshot(self.request(), self.state)
        with self.assertRaises(signing.BadSignature):
            read_snapshot(self.request(), token[:50] + 'AA' + token[52:])

    def test_preview_requires_exact_authorized_role(self):
        for role in (18, 7, 8):
            self.assertTrue(self.access(role=role).can_preview)
        for role in (20, 22):
            request = self.request(access=self.access(role=role))
            self.assertFalse(request.acm_access.can_preview)
            with self.assertRaises(PermissionDenied):
                set_perspective(request, 18)

    @patch('acm.access.role_catalog', return_value=ROLES)
    def test_switch_changes_view_without_changing_identity(self, catalog):
        request = self.request(access=self.access(role=7))
        set_perspective(request, 20)
        self.assertEqual(request.session['acm_role_perspective']['role_id'], 20)
        self.assertEqual(request.acm_access.user.pk, '77')
        self.assertEqual(request.acm_access.own_role['id'], 7)
        set_perspective(request, 0)
        self.assertEqual(request.session['acm_role_perspective']['role_id'], 7)

    def test_developer_cannot_manage_policy_even_when_previewing_administrator(self):
        request = self.request(access=self.access(role=18, own=7))
        self.assertFalse(request.acm_access.can_configure)
        with self.assertRaises(PermissionDenied):
            portal_views.role_policy(request, 20)

    def test_administrator_has_all_capabilities(self):
        self.assertTrue(all(self.access(role=18).permissions.values()))

    @patch('cuadrantizacion.map_layers.map_layers_config')
    def test_general_manager_without_polygon_permission_cannot_refresh_layers(self, layers):
        ACMRolePolicy.objects.create(role_id=8, permissions={'pdm_polygons': False}, updated_by='77')
        access = self.access(role=8, own=18)
        access.user.is_superuser = True
        response = portal_views.map_layers(self.request('/acm/capas-mapa/', access=access))
        self.assertEqual(response.status_code, 403)
        layers.assert_not_called()

    @patch('cuadrantizacion.map_layers.map_layers_config')
    def test_enabled_role_can_refresh_layers_in_its_own_session(self, layers):
        ACMRolePolicy.objects.create(role_id=8, permissions={'pdm_polygons': True}, updated_by='77')
        layers.return_value = {'raster': [], 'vectoriales': [{'id': 1}], 'zonas': []}
        response = portal_views.map_layers(self.request('/acm/capas-mapa/', access=self.access(role=8)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), layers.return_value)
        self.assertEqual(response['Cache-Control'], 'no-store')
        layers.assert_called_once_with(include_zones=True)

    @patch('cuadrantizacion.map_layers.map_layers_config')
    def test_anonymous_map_layer_request_is_rejected(self, layers):
        request = self.factory.get('/acm/capas-mapa/')
        request.session = {}
        self.assertEqual(portal_views.map_layers(request).status_code, 401)
        layers.assert_not_called()

    @patch('acm.access.role_catalog', return_value=ROLES)
    @patch('cuadrantizacion.map_layers.map_layers_config')
    def test_disabled_role_page_does_not_load_polygon_scripts_or_layer_data(self, layers, catalog):
        response = components_views.page(self.request(access=self.access(role=8, own=18)))
        self.assertEqual(response.status_code, 200)
        for script in ('js/capas-mapa.js', 'js/capa-vectorial.js', 'js/capa-raster-overlay.js', 'zonas-mapa-data'):
            self.assertNotIn(script, response.content.decode())
        layers.assert_not_called()

    def test_new_unknown_permission_never_enabled_for_basic(self):
        ACMRolePolicy.objects.create(role_id=20, permissions={'unknown_future_feature': True}, updated_by='1')
        flags, _ = policy_for(ROLES[3])
        self.assertNotIn('unknown_future_feature', flags)
        self.assertFalse(flags['portal_names'])

    @patch('acm.portal_views.role_catalog', return_value=ROLES)
    def test_policy_save_is_audited_and_rejects_stale_updates(self, catalog):
        values = dict(DEFAULTS, portal_names=True, portal_pins=True, publication=True)
        request = self.request(method='post', data={'permissions': values, 'revision': 0}, access=self.access(role=18))
        response = portal_views.role_policy(request, 20)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ACMRoleAudit.objects.get().actor_id, '77')
        self.assertEqual(portal_views.role_policy(request, 20).status_code, 409)
        flags, revision = policy_for(ROLES[3])
        self.assertTrue(flags['portal_pins'])
        self.assertEqual(revision, 1)

    @patch('acm.portal_views.role_catalog', return_value=ROLES)
    def test_policy_rejects_origin_leak_dependencies(self, catalog):
        values = dict(DEFAULTS, publication=True)
        response = portal_views.role_policy(self.request(method='post', data={'permissions': values, 'revision': 0}, access=self.access(role=18)), 20)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ACMRolePolicy.objects.exists())

    def test_foreign_history_cannot_be_replicated_deleted_or_downloaded(self):
        row, _ = persist_history(ACMIdentity('other', 'other'), self.p, self.rows, self.result)
        for view in (components_views.replicate_history, components_views.history_pdf_report,
                     components_views.history_word_report, portal_views.delete_analysis):
            request = self.request(method='post' if view is portal_views.delete_analysis else 'get')
            with self.assertRaises(Http404):
                view(request, row.pk)

    def test_history_is_saved_under_propify_id_and_not_duplicated(self):
        row, created = persist_history(ACMIdentity('77', 'name'), self.p, self.rows, self.result)
        again, duplicated = persist_history(ACMIdentity('77', 'renamed'), self.p, self.rows, self.result)
        self.assertTrue(created)
        self.assertFalse(duplicated)
        self.assertEqual(row.pk, again.pk)
        self.assertEqual(row.owner_id, '77')

    def test_prometeo_session_does_not_authenticate_acm(self):
        request = self.factory.get('/acm/analisis/')
        request.session = {}
        request.current_user = SimpleNamespace(is_authenticated=True, is_active=True)
        self.assertIsNone(get_access(request))
        self.assertEqual(components_views.page(request).status_code, 302)

    def test_forged_adjustment_rejected_by_server(self):
        request = self.request(method='post', data={'manual_valuation': 123456})
        request.acm_access.permissions['adjust_valuation'] = False
        self.assertEqual(components_views.recalculate(request).status_code, 403)
        request = self.request(method='post', data={'target_areas': {'land': 20, 'built': 20}})
        self.assertEqual(components_views.recalculate(request).status_code, 403)

    @patch('acm.components_views.load_records')
    def test_search_and_recalculate_use_opaque_selection_without_losing_values(self, loader):
        loader.return_value = (self.rows, [])
        request = self.request(method='post', data=params())
        response = components_views.search(request)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['result']['new']['total'], self.result['new']['total'])
        self.assertNotIn('remax', json.dumps(data).lower())
        selected = [data['records'][0]['id']]
        recalc = components_views.recalculate(self.request(method='post', data={'token': data['token'], 'excluded': selected}))
        self.assertEqual(recalc.status_code, 200)
        state, excluded = components_views._signed_selection(self.request(method='post', data={'token': data['token'], 'excluded': selected}))
        self.assertEqual(excluded, [self.rows[0]['id']])
        self.assertEqual(state['records'], self.rows)

    @patch('acm.components_views.load_records')
    def test_disabled_calculation_never_queries_sources(self, loader):
        access = self.access()
        access.permissions['calculate'] = False
        response = components_views.search(self.request(method='post', data=params(), access=access))
        self.assertEqual(response.status_code, 403)
        loader.assert_not_called()

    @patch('acm.access.role_catalog', return_value=ROLES)
    def test_role_settings_and_analysis_templates_render_with_separate_menu(self, catalog):
        response = portal_views.role_settings(self.request(access=self.access(role=18)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tipo de usuario')
        self.assertContains(response, 'Configuración de accesos')
        self.assertNotContains(response, 'Admin Django')
        response = components_views.page(self.request(access=self.access(role=20, own=7)))
        self.assertContains(response, 'Vista activa:')
        self.assertContains(response, 'Agente No Afiliado')
        self.assertContains(response, 'Cambiar rol')
        self.assertNotContains(response, 'name="source" value="remax"')
        self.assertNotContains(response, 'acm/js/nearby-places.js')
        self.assertNotContains(response, 'acm/js/zona-preevaluacion.js')

    def test_explicit_logout_does_not_reuse_other_propify_session(self):
        request = self.factory.get('/acm/')
        request.session = {'acm_logged_out': True, 'prospects_propify_access_token': 'not-a-real-token', 'prospects_propify_profile': {'id': 77}}
        self.assertIsNone(get_access(request))

    def test_report_projection_strips_provider_even_from_old_ai_explanation(self):
        state = copy.deepcopy(self.state)
        state['params']['proposal_explanation'] = 'REMAX https://remax.pe/casa'
        safe, result, excluded = project(self.request(), state, self.result, report=True)
        from .components_html import build_acm_html
        html = build_acm_html(safe['params'], safe['records'], result, excluded)
        self.assertNotIn('remax', html.lower())
        self.assertNotIn('<th>Publicación</th>', html)

    def test_record_named_like_a_field_does_not_corrupt_measurements(self):
        state = copy.deepcopy(self.state)
        state['records'][0]['id'] = 'land'
        state['params']['weight_reference'] = {'land': 150, 'built': 200}
        safe, _, _ = project(self.request(), state)
        self.assertEqual(safe['params']['weight_reference']['land'], 150)
        self.assertEqual(safe['records'][0]['land'], state['records'][0]['land'])

    def test_real_propify_role_is_read_from_database_not_session_flags(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (77, 'agent', '', '', 20, 'Agente No Afiliado', False)
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        request = self.factory.get('/acm/analisis/')
        request.session = {'acm_propify_profile': {'id': 77, 'role': 'Administrador', 'is_superuser': True}, 'acm_propify_token': 'fixture'}
        with patch('acm.access.connections', {'propifai': connection}):
            access = get_access(request)
        self.assertFalse(access.can_configure)
        self.assertFalse(access.can_preview)
        self.assertEqual(access.role['id'], 20)

    def test_inactive_propify_user_is_denied(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        request = self.factory.get('/acm/analisis/')
        request.session = {'acm_propify_profile': {'id': 77}, 'acm_propify_token': 'fixture'}
        with patch('acm.access.connections', {'propifai': connection}):
            self.assertIsNone(get_access(request))

    @patch('acm.portal_views.requests.post')
    def test_login_keeps_prometeo_identity_separate(self, post):
        from django.contrib.sessions.backends.signed_cookies import SessionStore
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'access': 'fixture-not-a-real-token', 'user': {'id': 77, 'username': 'agent'}}
        request = self.factory.post('/acm/login/', {'username': 'agent', 'password': 'fixture', 'next': '/acm/analisis/'})
        request.session = SessionStore()
        request.session['existing_prometeo_identity'] = 'unchanged'
        request._dont_enforce_csrf_checks = True
        response = portal_views.login(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(request.session['acm_propify_profile']['id'], 77)
        self.assertEqual(request.session['existing_prometeo_identity'], 'unchanged')
        self.assertNotIn('_auth_user_id', request.session)

    @patch('acm.portal_views.requests.post')
    def test_failed_login_does_not_create_identity_or_echo_password(self, post):
        from django.contrib.sessions.backends.signed_cookies import SessionStore
        post.return_value.status_code = 401
        request = self.factory.post('/acm/login/', {'username': 'agent', 'password': 'fixture-private-password'})
        request.session = SessionStore()
        request._dont_enforce_csrf_checks = True
        response = portal_views.login(request)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('acm_propify_profile', request.session)
        self.assertNotContains(response, 'fixture-private-password')

    def test_role_setting_post_requires_csrf(self):
        request = self.request('/acm/configuracion/roles/20/', method='post', data={'permissions': dict(DEFAULTS), 'revision': 0}, access=self.access(role=18))
        request._dont_enforce_csrf_checks = False
        self.assertEqual(portal_views.role_policy(request, 20).status_code, 403)

    def test_unknown_metadata_and_branded_location_text_are_not_exposed(self):
        state = copy.deepcopy(self.state)
        state['records'][0].update(provider_private_metadata='Remax', original_url='https://remax.pe', district='Zona Remax')
        safe, _, _ = project(self.request(), state)
        serialized = json.dumps(safe['records']).lower()
        self.assertNotIn('remax', serialized)
        self.assertNotIn('provider_private_metadata', serialized)
        self.assertNotIn('original_url', serialized)

    def test_photo_approval_survives_a_new_azure_signature(self):
        one = 'https://granextractormedia.blob.core.windows.net/photos/one.jpg?sig=one&se=yesterday'
        two = 'https://granextractormedia.blob.core.windows.net/photos/one.jpg?sig=two&se=tomorrow'
        self.assertEqual(photo_digest(one), photo_digest(two))
        self.assertNotEqual(photo_digest(one), photo_digest(two.replace('/one.jpg', '/two.jpg')))

    @patch('acm.access.role_catalog', return_value=ROLES)
    def test_own_history_replay_preserves_parameters_and_escapes_address(self, catalog):
        p = dict(self.p, rooms=0, baths=2.5, address='</script><script>fixture</script>')
        row, _ = persist_history(ACMIdentity('77', 'owner'), p, self.rows, self.result)
        before = copy.deepcopy(row.snapshot)
        response = components_views.replicate_history(self.request(), row.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cmp-replication-data')
        self.assertNotContains(response, '</script><script>fixture</script>')
        row.refresh_from_db()
        self.assertEqual(row.snapshot, before)
        self.assertEqual(ACMPortalAnalysis.objects.count(), 1)

    def test_verified_history_import_is_dry_run_then_idempotent(self):
        import tempfile
        import uuid
        from pathlib import Path
        from django.core.management import call_command
        from django.utils import timezone
        command = 'acm.management.commands.import_acm_propify_history'
        legacy = SimpleNamespace(id=uuid.uuid4(), metodo='componentes', parametros_json=self.p,
                                 propiedades_json=self.rows, resultado_json=self.result, created_at=timezone.now())
        cursor = MagicMock()
        cursor.fetchone.return_value = (77,)
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        with tempfile.TemporaryDirectory() as directory:
            mapping = Path(directory) / 'verified.json'
            mapping.write_text(json.dumps([{'prometeo_user_id': str(uuid.uuid4()), 'propify_user_id': 77}]))
            with patch(command+'.connections', {'propifai': connection}), patch(command+'.ACMLink.objects.filter') as history:
                history.return_value.iterator.return_value = [legacy]
                from io import StringIO
                call_command('import_acm_propify_history', mapping=str(mapping), stdout=StringIO())
                self.assertEqual(ACMPortalAnalysis.objects.count(), 0)
                for _ in range(2):
                    call_command('import_acm_propify_history', mapping=str(mapping), apply=True, stdout=StringIO())
                self.assertEqual(ACMPortalAnalysis.objects.count(), 1)
                self.assertEqual(ACMPortalAnalysis.objects.get().owner_id, '77')

    def test_portal_homepage_and_specific_publication_have_independent_permissions(self):
        access = self.access()
        access.permissions.update(portal_names=True, portal_link=True, publication=False)
        safe, _, _ = project(self.request(access=access), self.state)
        self.assertEqual(safe['records'][0]['url'], '')
        self.assertEqual(safe['records'][0]['portal_url'], 'https://remax.pe/')
        access.permissions.update(portal_link=False, publication=True)
        safe, _, _ = project(self.request(access=access), self.state)
        self.assertEqual(safe['records'][0]['url'], 'https://remax.pe/casa')
        self.assertNotIn('portal_url', safe['records'][0])

    def test_pdf_photographs_are_fetched_only_when_the_permission_is_enabled(self):
        from io import BytesIO
        from PIL import Image
        from .components_pdf import build_acm_pdf
        stream = BytesIO()
        Image.new('RGB', (2, 2), 'white').save(stream, format='JPEG')
        with patch('acm.components_pdf._static_map', return_value=None), patch('acm.components_pdf._reverse_geocode', return_value='Ubicación'), patch('acm.portal_views.load_photo_bytes', return_value=stream.getvalue()) as load:
            for allowed in (False, True):
                load.reset_mock()
                p = dict(self.p, _acm_permissions={'report_photos': allowed, 'publication_dates': False})
                pdf = build_acm_pdf(p, self.rows, self.result, fetch_images=True)
                self.assertTrue(pdf.startswith(b'%PDF'))
                self.assertEqual(load.called, allowed)

    @patch('ingestas.ml_model_views.estimate')
    def test_published_model_uses_acm_identity_and_hides_training_metadata(self, estimate):
        from django.http import JsonResponse
        access = self.access()
        access.permissions['ai'] = True
        request = self.request(method='post', access=access)
        request.current_user = None
        def result(inner):
            self.assertEqual(inner.current_user.pk, '77')
            return JsonResponse({'available': True, 'price_usd': 100000, 'run_id': 1, 'dataset_id': 2, 'sample': 30})
        estimate.side_effect = result
        response = portal_views.model_estimate(request)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['price_usd'], 100000)
        self.assertNotIn('dataset_id', data)
        self.assertIsNone(request.current_user)

    @patch('ingestas.ml_model_views.estimate')
    def test_disabled_ai_never_calls_published_model(self, estimate):
        response = portal_views.model_estimate(self.request(method='post'))
        self.assertEqual(response.status_code, 403)
        estimate.assert_not_called()
