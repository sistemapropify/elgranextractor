import json
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch
from datetime import timedelta
from django.test import SimpleTestCase, RequestFactory, TestCase
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from django.middleware.csrf import CsrfViewMiddleware
from django.template.loader import get_template
from ingestas.views import ScrapingVerificationView
from ingestas.scraping_verification import active_for_job, valid_answer
from ingestas.scraping_verification import submit_answer
from ingestas.scraping_verification import mailbox, public_state
from ingestas.models import ScrapingJob, EjecucionPortal


class VerificationMailboxTests(TestCase):
    def setUp(self):
        self.job = ScrapingJob.objects.create(estado='running', execution_token=uuid.uuid4(),
            lease_expires_at=timezone.now() + timedelta(minutes=5))
        self.run = EjecucionPortal.objects.create(job=self.job, portal='adondevivir')
        self.exchange = mailbox(self.run.pk, self.job.execution_token)
        self.challenge = self.exchange('open', screenshot='png', seconds=120)

    def test_screen_stays_visible_until_browser_finishes_action(self):
        self.assertEqual(public_state(self.job)['state'], 'waiting')
        submit_answer(self.job.pk, self.challenge, 'c:200:100')
        self.assertEqual(public_state(self.job)['state'], 'submitted')
        self.assertEqual(self.exchange('poll', id=self.challenge), 'c:200:100')
        self.assertEqual(public_state(self.job)['state'], 'consumed')
        self.assertIsNone(self.exchange('poll', id=self.challenge))
        self.exchange('executed', id=self.challenge)
        state = public_state(self.job)
        self.assertEqual(state['state'], 'executed')
        self.assertEqual(state['screenshot'], 'png')
        self.assertNotIn('answer', state)
        self.assertNotIn('execution_token', state)
        with self.assertRaises(ValueError):
            submit_answer(self.job.pk, self.challenge, 'c:200:100')
        next_id = self.exchange('open', screenshot='next', seconds=100)
        self.assertEqual(public_state(self.job)['id'], next_id)
        self.assertEqual(public_state(self.job)['state'], 'waiting')
        self.exchange('close')
        self.assertIsNone(public_state(self.job))

    def test_cannot_confirm_unconsumed_action(self):
        with self.assertRaises(ValueError):
            self.exchange('executed', id=self.challenge)
        self.assertEqual(public_state(self.job)['state'], 'waiting')

    def test_post_click_feedback_updates_screen_without_unlocking_action(self):
        with self.assertRaises(ValueError):
            self.exchange('feedback', id=self.challenge, screenshot='after-click')
        submit_answer(self.job.pk, self.challenge, 'c:200:100')
        self.exchange('poll', id=self.challenge)
        self.exchange('executed', id=self.challenge)
        self.exchange('feedback', id=self.challenge, screenshot='after-click')
        state = public_state(self.job)
        self.assertEqual(state['id'], self.challenge)
        self.assertEqual(state['state'], 'executed')
        self.assertEqual(state['screenshot'], 'after-click')
        with self.assertRaises(ValueError):
            submit_answer(self.job.pk, self.challenge, 'c:200:100')

    def test_automatic_capture_rotates_id_without_extending_deadline(self):
        expiry = public_state(self.job)['expires_at']
        next_id = self.exchange('refresh', id=self.challenge, screenshot='new-screen')
        self.assertNotEqual(next_id, self.challenge)
        state = public_state(self.job)
        self.assertEqual(state['id'], next_id)
        self.assertEqual(state['screenshot'], 'new-screen')
        self.assertEqual(state['expires_at'], expiry)
        with self.assertRaises(ValueError):
            submit_answer(self.job.pk, self.challenge, 'c:200:100')
        submit_answer(self.job.pk, next_id, 'c:300:200')
        self.assertEqual(self.exchange('poll', id=next_id), 'c:300:200')

    def test_answer_submitted_during_capture_is_not_discarded(self):
        submit_answer(self.job.pk, self.challenge, 'c:200:100')
        self.assertIsNone(self.exchange('refresh', id=self.challenge, screenshot='new-screen'))
        self.assertEqual(public_state(self.job)['screenshot'], 'png')
        self.assertEqual(self.exchange('poll', id=self.challenge), 'c:200:100')

    def test_automatic_capture_cannot_replace_a_consumed_or_executed_action(self):
        submit_answer(self.job.pk, self.challenge, 'c:200:100')
        self.exchange('poll', id=self.challenge)
        self.assertIsNone(self.exchange('refresh', id=self.challenge, screenshot='new-screen'))
        self.exchange('executed', id=self.challenge)
        self.assertIsNone(self.exchange('refresh', id=self.challenge, screenshot='new-screen'))
        self.assertEqual(public_state(self.job)['id'], self.challenge)

    def test_automatic_capture_is_not_enabled_for_properati(self):
        self.run.portal = 'properati'
        self.run.save(update_fields=['portal'])
        with self.assertRaises(ValueError):
            self.exchange('refresh', id=self.challenge, screenshot='new-screen')
        self.assertEqual(public_state(self.job)['id'], self.challenge)

    def test_properati_does_not_expose_submitted_answer_screen(self):
        self.run.portal = 'properati'
        self.run.save(update_fields=['portal'])
        submit_answer(self.job.pk, self.challenge, '12')
        self.assertIsNone(public_state(self.job))


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

    def test_adondevivir_action_validated_against_actual_portal(self):
        item = SimpleNamespace(pk='challenge', run=SimpleNamespace(portal='adondevivir'))
        query = Mock()
        query.filter.return_value.select_related.return_value.first.return_value = item
        query.filter.return_value.update.return_value = 1
        with patch('ingestas.scraping_verification.ScrapingJob'), \
             patch('ingestas.scraping_verification.active_for_job', return_value=query):
            submit_answer.__wrapped__(1, 'challenge', 'c:100:200')
            query.filter.return_value.update.assert_called_once_with(answer='c:100:200', state='submitted')
            with self.assertRaises(ValueError): submit_answer.__wrapped__(1, 'challenge', 'c:8192:20')

    def test_click_cannot_be_sent_to_properati(self):
        item = SimpleNamespace(pk='challenge', run=SimpleNamespace(portal='properati'))
        query = Mock()
        query.filter.return_value.select_related.return_value.first.return_value = item
        with patch('ingestas.scraping_verification.ScrapingJob'), \
             patch('ingestas.scraping_verification.active_for_job', return_value=query):
            with self.assertRaises(ValueError): submit_answer.__wrapped__(1, 'challenge', 'c:100:200')
            query.filter.return_value.update.assert_not_called()

    def test_missing_or_consumed_challenge_rejects_click(self):
        query = Mock()
        query.filter.return_value.select_related.return_value.first.return_value = None
        with patch('ingestas.scraping_verification.ScrapingJob'), \
             patch('ingestas.scraping_verification.active_for_job', return_value=query):
            with self.assertRaises(ValueError): submit_answer.__wrapped__(1, 'challenge', 'c:100:200')
            query.filter.return_value.update.assert_not_called()

    def test_template_compiles(self):
        self.assertIsNotNone(get_template('ingestas/scraping_dashboard.html'))
