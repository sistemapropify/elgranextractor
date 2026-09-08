"""Regression for Prometeo session -> login -> scraping redirect loops."""
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from intelligence.models import Role, User
from ingestas.views import ScrapingDashboardView, ScrapingControlView, ScrapingStatusView, ScrapingStreamView


@override_settings(
    LOGIN_URL='/login/',
    MIDDLEWARE=[
        'django.contrib.sessions.middleware.SessionMiddleware',
        'intelligence.middleware.AuthenticationMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
    ],
)
class ScrapingSessionAccessTests(TestCase):
    def setUp(self):
        role = Role.objects.create(name='Scraping test', default_level=1, max_level=1)
        self.user = User.objects.create(role=role, username='scraping_session', phone='scraping_session', is_active=True)
        session = self.client.session
        session['user_id'] = str(self.user.pk)
        session.save()
        self.dashboard = reverse('ingestas:scraping_dashboard')

    def test_existing_prometeo_cookie_reaches_dashboard_without_login_loop(self):
        # Use the production middleware, login view and dashboard dispatch;
        # replace only template rendering/data loading, unrelated to auth.
        with patch.object(ScrapingDashboardView, 'get', return_value=HttpResponse('dashboard')):
            response = self.client.get('/login/', {'next': self.dashboard}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [(self.dashboard, 302)])
        self.assertContains(response, 'dashboard')

    def test_same_session_authorizes_controls_status_and_logs(self):
        endpoints = [(ScrapingControlView, 'post', {}), (ScrapingStatusView, 'get', {'job_id': 1}),
                     (ScrapingStreamView, 'get', {'job_id': 1})]
        for view, method, kwargs in endpoints:
            with self.subTest(view=view.__name__):
                request = getattr(RequestFactory(), method)('/ingestas/scraping/control/')
                request.current_user = self.user
                request.user = AnonymousUser()
                with patch.object(view, method, return_value=HttpResponse('ok')):
                    self.assertEqual(view.as_view()(request, **kwargs).status_code, 200)

    def test_anonymous_request_stops_at_login_form(self):
        response = Client().get(self.dashboard, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.redirect_chain), 1)
        self.assertTrue(response.redirect_chain[0][0].startswith('/login/?next='))

    def test_session_does_not_bypass_csrf_for_controls(self):
        client = Client(enforce_csrf_checks=True)
        client.cookies = self.client.cookies
        response = client.post(reverse('ingestas:scraping_control'), {'action': 'start'})
        self.assertEqual(response.status_code, 403)

    def test_inactive_prometeo_user_is_not_authorized(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        request = RequestFactory().get(self.dashboard)
        request.user = AnonymousUser()
        request.current_user = self.user
        self.assertEqual(ScrapingDashboardView.as_view()(request).status_code, 302)
        response = self.client.get(self.dashboard, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.redirect_chain), 1)
