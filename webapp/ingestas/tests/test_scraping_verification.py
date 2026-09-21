import json
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch
from datetime import timedelta
from django.test import SimpleTestCase, RequestFactory
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from django.middleware.csrf import CsrfViewMiddleware
from django.template.loader import get_template
from ingestas.views import ScrapingVerificationView
from ingestas.scraping_verification import active_for_job, valid_answer


class VerificationAccessTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_anonymous_cannot_read_screenshot(self):
        request = self.factory.get('/ingestas/scraping/verificacion/1/')
        request.user = AnonymousUser()
        with patch('ingestas.scraping_verification.public_state') as read:
            response = ScrapingVerificationView.as_view()(request, job_id=1)
        self.assertEqual(response.status_code, 302)
        read.assert_not_called()

    def test_post_is_csrf_protected(self):
        request = self.factory.post('/ingestas/scraping/verificacion/1/', {'answer': '123'})
        request.user = SimpleNamespace(is_authenticated=True)
        self.assertEqual(CsrfViewMiddleware(lambda r: None).process_view(
            request, ScrapingVerificationView.as_view(), (), {'job_id': 1}).status_code, 403)

    def test_prometeo_session_can_get_only_public_state(self):
        request = self.factory.get('/ingestas/scraping/verificacion/1/')
        request.user = AnonymousUser()
        request.current_user = SimpleNamespace(is_active=True)
        with patch('ingestas.views.get_object_or_404', return_value=Mock()), \
             patch('ingestas.scraping_verification.public_state', return_value={'id': 'x', 'screenshot': 'png'}):
            response = ScrapingVerificationView.as_view()(request, job_id=1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertNotIn('execution_token', json.loads(response.content))

    def test_stale_answer_is_rejected(self):
        request = self.factory.post('/ingestas/scraping/verificacion/1/', {
            'verification_id': str(uuid.uuid4()), 'answer': '123'})
        request.current_user = SimpleNamespace(is_active=True)
        with patch('ingestas.scraping_verification.submit_answer', side_effect=ValueError('vencida')):
            response = ScrapingVerificationView.as_view()(request, job_id=1)
        self.assertEqual(response.status_code, 409)

    def test_inactive_jobs_expose_no_browser(self):
        job = SimpleNamespace(estado='stopped', execution_token=uuid.uuid4(), lease_expires_at=timezone.now())
        with patch('ingestas.scraping_verification.ScrapingVerification') as model:
            active_for_job(job)
            model.objects.none.assert_called_once()
            model.objects.filter.assert_not_called()

    def test_active_filter_fences_execution_and_expiry(self):
        job = SimpleNamespace(pk=3, estado='running', execution_token=uuid.uuid4(),
                              lease_expires_at=timezone.now() + timedelta(seconds=180))
        with patch('ingestas.scraping_verification.ScrapingVerification') as model:
            active_for_job(job)
            filters = model.objects.filter.call_args.kwargs
        self.assertEqual(filters['execution_token'], job.execution_token)
        self.assertEqual(filters['run__job_id'], 3)
        self.assertIn('expires_at__gt', filters)

    def test_answer_is_bounded_and_numeric(self):
        self.assertTrue(valid_answer('-12'))
        for answer in ('', '1e100', '1;click()', '9' * 20):
            self.assertFalse(valid_answer(answer))

    def test_template_compiles(self):
        self.assertIsNotNone(get_template('ingestas/scraping_dashboard.html'))
