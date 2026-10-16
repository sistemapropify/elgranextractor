"""Exercise response-time session persistence; mock only the remote login API."""
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from django.contrib.sessions.backends.db import SessionStore as SQLSessionStore
from django.contrib.sessions.backends.signed_cookies import SessionStore as CookieSessionStore
from django.db import DatabaseError
from django.http import HttpResponse, HttpResponseForbidden
from django.test import Client, RequestFactory, SimpleTestCase, override_settings

from .access import SESSION_PROFILE, SESSION_TOKEN
from .session_backend import SessionStore
from .session_middleware import ACMSessionMiddleware, COOKIE_NAME


class ACMSessionTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.overrides = override_settings(ACM_SESSION_FILE_PATH=self.directory.name)
        self.overrides.enable()
        self.addCleanup(self.overrides.disable)
        self.middleware = ACMSessionMiddleware(lambda request: HttpResponse())
        self.factory = RequestFactory()

    def login_response(self, client):
        with patch('acm.portal_views.requests.post', return_value=MagicMock(
                status_code=200, json=lambda: {'access': 'fixture-server-token', 'user': {'id': 77, 'username': 'agent'}})):
            return client.post('/acm/login/', {'username': 'agent', 'password': 'fixture-password'})

    @override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
    def test_login_saves_session_even_when_sql_cannot_write(self):
        client = Client()
        client.cookies['sessionid'] = 'unrelated-prometeo-cookie'
        with patch.object(SQLSessionStore, 'save', side_effect=DatabaseError('database size quota')) as save:
            response = self.login_response(client)
        self.assertEqual(response.status_code, 302)
        save.assert_not_called()
        self.assertNotIn('sessionid', response.cookies)
        self.assertEqual(client.cookies['sessionid'].value, 'unrelated-prometeo-cookie')
        cookie = response.cookies[COOKIE_NAME]
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['path'], '/')
        self.assertEqual(len(cookie.value), 32)
        self.assertNotIn('fixture', cookie.value)
        session = SessionStore(cookie.value)
        self.assertEqual(session[SESSION_PROFILE]['id'], 77)
        self.assertEqual(session[SESSION_TOKEN], 'fixture-server-token')

    def test_two_logins_from_same_cookie_both_complete_with_valid_sessions(self):
        original = SessionStore()
        original['before_login'] = True
        original.save()
        clients = [Client(), Client()]
        keys = []
        for client in clients:
            client.cookies[COOKIE_NAME] = original.session_key
            response = self.login_response(client)
            self.assertEqual(response.status_code, 302)
            keys.append(response.cookies[COOKIE_NAME].value)
        self.assertNotEqual(keys[0], keys[1])
        for key in keys:
            self.assertEqual(SessionStore(key)[SESSION_PROFILE]['id'], 77)
        self.assertFalse(SessionStore(original.session_key).exists(original.session_key))

    def test_logout_revokes_own_session_without_touching_prometeo(self):
        client = Client()
        self.login_response(client)
        key = client.cookies[COOKIE_NAME].value
        client.cookies['sessionid'] = 'unrelated-prometeo-cookie'
        response = client.post('/acm/logout/')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SessionStore(key).exists(key))
        self.assertNotIn('sessionid', response.cookies)
        new_key = client.cookies[COOKIE_NAME].value
        self.assertNotIn(SESSION_TOKEN, SessionStore(new_key))

    def test_revoked_inflight_session_never_recreated(self):
        session = SessionStore()
        session[SESSION_TOKEN] = 'fixture-server-token'
        session.save()
        request = self.factory.post('/api/acm/search/')
        request.COOKIES[COOKIE_NAME] = session.session_key
        self.middleware.process_request(request)
        self.assertEqual(request.session[SESSION_TOKEN], 'fixture-server-token')
        session.delete()
        request.session['changed'] = True
        response = self.middleware.process_response(request, HttpResponse())
        self.assertEqual(response.status_code, 409)
        self.assertNotIn(COOKIE_NAME, response.cookies)
        self.assertFalse(SessionStore(session.session_key).exists(session.session_key))

    def test_other_modules_keep_default_session_backend_and_cookie(self):
        request = self.factory.get('/marketing/prospeccion/')
        self.middleware.process_request(request)
        self.assertIsInstance(request.session, CookieSessionStore)
        request.session['prometeo'] = True
        response = self.middleware.process_response(request, HttpResponse())
        self.assertIn('sessionid', response.cookies)
        self.assertNotIn(COOKIE_NAME, response.cookies)

    def test_csrf_still_required_for_login(self):
        client = Client(enforce_csrf_checks=True)
        # Avoid Django 5.0's template-instrumentation incompatibility with
        # Python 3.14 when rendering its default 403 page. CSRF runs unchanged.
        failure = lambda request, reason='': HttpResponseForbidden()
        with patch('acm.portal_views.requests.post') as post, patch('django.middleware.csrf._get_failure_view', return_value=failure):
            response = client.post('/acm/login/', {'username': 'agent', 'password': 'fixture'})
        self.assertEqual(response.status_code, 403)
        post.assert_not_called()

    @override_settings(SESSION_COOKIE_SECURE=True)
    def test_production_cookie_is_secure(self):
        response = self.login_response(Client())
        self.assertTrue(response.cookies[COOKIE_NAME]['secure'])

    def test_invalid_cookie_cannot_load_a_profile(self):
        self.assertEqual(dict(SessionStore('../../not-a-session')), {})

    def test_failing_storage_does_not_issue_authenticated_cookie(self):
        request = self.factory.get('/acm/')
        self.middleware.process_request(request)
        request.session[SESSION_TOKEN] = 'fixture-server-token'
        with patch.object(SessionStore, 'save', side_effect=OSError('disk full')), self.assertLogs('acm.session_middleware', level='ERROR'):
            response = self.middleware.process_response(request, HttpResponse())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(COOKIE_NAME, response.cookies)
