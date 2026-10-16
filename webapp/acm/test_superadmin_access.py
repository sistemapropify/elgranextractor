from unittest.mock import MagicMock, patch

from django.test import TestCase, RequestFactory

from .access import (SESSION_PROFILE, SESSION_TOKEN, SESSION_PREVIEW, get_access,
                     template_context, ACMAccess, ACMIdentity, DEFAULTS)
from .portal_views import role_settings, role_policy


class SuperadminAccessTests(TestCase):
    roles = [dict(id=7, name='Desarrollador', area='Tecnología', area_id=5, internal=True),
             dict(id=20, name='Agente No Afiliado', area='Agentes', area_id=8, internal=False)]

    def request(self, superuser=True, preview=False, session_claim=False):
        request = RequestFactory().get('/acm/configuracion/')
        request.session = {SESSION_PROFILE: {'id': 2, 'is_superuser': session_claim}, SESSION_TOKEN: 'fixture'}
        if preview:
            request.session[SESSION_PREVIEW] = {'owner':'2', 'role_id':20, 'nonce':'fixture'}
        cursor = MagicMock()
        cursor.fetchone.return_value = (2, 'fixture-admin', '', '', 7, 'Desarrollador', superuser)
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        with patch('acm.access.connections', {'propifai':connection}), patch('acm.access.role_catalog', return_value=self.roles):
            get_access(request)
        return request

    @patch('acm.access.role_catalog')
    def test_verified_superuser_with_developer_role_can_open_configuration(self, catalog):
        catalog.return_value = self.roles
        request = self.request()
        self.assertEqual(request.acm_access.own_role['name'], 'Desarrollador')
        self.assertTrue(request.acm_access.user.is_superuser)
        self.assertTrue(request.acm_access.can_configure)
        self.assertTrue(template_context(request)['show_acm_configuration'])
        response = role_settings(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Configuración de accesos')

    @patch('acm.portal_views.role_catalog')
    def test_verified_superuser_can_read_role_configuration(self, catalog):
        catalog.return_value = self.roles
        response = role_policy(self.request(), 20)
        self.assertEqual(response.status_code, 200)

    @patch('acm.access.role_catalog')
    def test_real_administration_remains_accessible_during_role_preview(self, catalog):
        catalog.return_value = self.roles
        request = self.request(preview=True)
        self.assertTrue(request.acm_access.previewing)
        self.assertTrue(template_context(request)['show_acm_configuration'])
        self.assertFalse(request.acm_access.permissions['portal_names'])

    def test_session_claim_does_not_grant_superuser_access(self):
        request = self.request(superuser=False, session_claim=True)
        self.assertFalse(request.acm_access.user.is_superuser)
        self.assertFalse(request.acm_access.can_configure)

    def test_ordinary_developer_previewing_administrator_is_still_not_admin(self):
        request = RequestFactory().get('/acm/configuracion/')
        request.acm_access = ACMAccess(ACMIdentity('77', 'fixture'), self.roles[0],
                                     dict(id=18, name='Administrador'), dict(DEFAULTS), 0, '')
        self.assertFalse(request.acm_access.can_configure)
