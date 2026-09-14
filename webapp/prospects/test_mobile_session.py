from unittest.mock import Mock, patch
from datetime import date
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from .propify_auth import PropifyAuthError, PropifyPrincipal, refresh_propify_session
from .models import MobileProspectUser
from . import control_api, mobile_api


class MobileAuthTests(SimpleTestCase):
    def request(self):
        return APIRequestFactory().get('/', HTTP_AUTHORIZATION='Bearer expired-test')

    def test_expired_access_is_401_not_403(self):
        with patch('prospects.propify_auth.principal_from_token', side_effect=PropifyAuthError('Sesión vencida', 401)):
            response = control_api.funnel(self.request())
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response['WWW-Authenticate'].startswith('Bearer'))

    def test_outage_does_not_expire_session(self):
        with patch('prospects.propify_auth.principal_from_token', side_effect=PropifyAuthError('No se pudo conectar', 503)):
            response = control_api.alerts(self.request())
        self.assertEqual(response.status_code, 503)

    def test_missing_access_is_401(self):
        self.assertEqual(control_api.alerts(APIRequestFactory().get('/')).status_code, 401)

    @override_settings(PROPIFY_AUTH_REFRESH_URL='https://api.propify.pe/api/auth/token/refresh/')
    def test_refresh_forwards_only_to_configured_propify(self):
        with patch('prospects.propify_auth.requests.post', return_value=Mock(status_code=200, json=lambda: {'access': 'new-access', 'refresh': 'rotated'})) as post:
            result = refresh_propify_session('old-refresh')
        self.assertEqual(result, {'access': 'new-access', 'refresh': 'rotated'})
        self.assertEqual(post.call_args.kwargs['json'], {'refresh': 'old-refresh'})
        self.assertFalse(post.call_args.kwargs['allow_redirects'])

    def test_refresh_endpoint_no_auth_required_and_no_cache(self):
        with patch('prospects.mobile_api.refresh_propify_session', return_value={'access': 'new', 'refresh': 'rotated'}):
            response = mobile_api.mobile_refresh(APIRequestFactory().post('/', {'refresh': 'old'}, format='json'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_expired_refresh_and_upstream_failure_are_distinct(self):
        for code in (401, 503):
            with patch('prospects.mobile_api.refresh_propify_session', side_effect=PropifyAuthError('test', code)):
                response = mobile_api.mobile_refresh(APIRequestFactory().post('/', {'refresh': 'old'}, format='json'))
            self.assertEqual(response.status_code, code)

    def test_refresh_rejects_invalid_input_without_network(self):
        for value in (None, [], 2, '', 'x'*16385):
            with patch('prospects.mobile_api.refresh_propify_session') as renew:
                response = mobile_api.mobile_refresh(APIRequestFactory().post('/', {'refresh': value}, format='json'))
            self.assertEqual(response.status_code, 400)
            renew.assert_not_called()


class MobileFunnelTests(TestCase):
    def test_funnel_uses_same_service_and_period_and_segments_as_web(self):
        user = MobileProspectUser.objects.create(username='supervisor-test', propify_user_id='10', can_view_crm_alerts=True)
        request = APIRequestFactory().get('/', {'from': '2026-09-07', 'to': '2026-09-08'})
        force_authenticate(request, user=PropifyPrincipal(user, {}, 'test'))
        with patch('prospects.control_api.get_management_dashboard', return_value={'selected_cohort': {'entered': 20}, 'captaciones_cohort': {'entered': 4}}) as dashboard:
            response = control_api.funnel(request)
        dashboard.assert_called_once_with(date(2026, 9, 7), date(2026, 9, 8), None)
        self.assertEqual(response.data['funnel']['entered'], 20)
        self.assertEqual(response.data['segments']['captaciones']['entered'], 4)

    def test_true_permissions_are_preserved(self):
        user = MobileProspectUser.objects.create(username='unlinked-test', propify_user_id='11')
        request = APIRequestFactory().get('/')
        force_authenticate(request, user=PropifyPrincipal(user, {}, 'valid'))
        with patch('prospects.control_api.get_management_dashboard') as dashboard:
            self.assertEqual(control_api.funnel(request).status_code, 403)
        dashboard.assert_not_called()
